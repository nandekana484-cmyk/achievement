"""実績の引き継ぎ(AD-16): 出し直しでキッティングNo.が変わった計画へ、管理者が確定して実績を移す。"""

import csv
import io
import json

import pytest

from app.core import clock
from app.db.models import ActualsExport, KittingHandover, Plan, RunCompletion, RunEvent, RunInput
from app.db.session import get_sessionmaker
from app.services import admin_auth, masters
from legacy_fixture import insert_plan, set_stale
from records_helpers import K1, K2, count_rows, end, new_session, ok, rid, start, sync_plans

H = {"X-Genba-Admin": "1"}
LOGIN = {"worker_id": "K0042", "password": "right-pass-1"}
NEW = "0722-1-S-251014-09"  # K1 を出し直したキッティングNo.(ロットNo.・ファイルNo.・回が同じ)
DAY = "2026-10-21"


@pytest.fixture
def admin(client, staffed):
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", "right-pass-1")
    return staffed


def login(client):
    assert client.post("/api/admin/login", json=LOGIN, headers=H).status_code == 200


def complete_k1(client, fake_clock, qty=150):
    """K1 を 9:00 から生産(良品 qty)、片付けまで進めて完了にする。"""
    fake_clock.advance(minutes=60)
    ok(start(client, "production"))
    fake_clock.advance(minutes=60)
    ok(end(client, "production", produced_qty=qty))
    ok(start(client, "cleanup"))
    fake_clock.advance(minutes=10)
    ok(end(client, "cleanup"))


def reissue(world, replacement=NEW, reason="stale"):
    """K1 が出し直されて古くなり、NEW が発行された状態にして同期する。"""
    insert_plan(world["db"], kitting_no=NEW, file_no="0722")
    set_stale(world["db"], K1, "L001", reason, replacement=replacement)
    sync_plans(world["app"])


def pending(client):
    login(client)
    return ok(client.get("/api/admin/handovers"))


def confirm(client, old=K1, new=NEW):
    login(client)
    return client.post("/api/admin/handovers/confirm", json={"old_kitting_no": old, "new_kitting_no": new}, headers=H)


def test_stale_plan_with_actuals_appears_with_candidates(client, admin, fake_clock):
    complete_k1(client, fake_clock)
    reissue(admin)
    items = pending(client)["items"]
    assert [i["kitting_no"] for i in items] == [K1]
    item = items[0]
    assert (item["reason"], item["completed"], item["replacement_count"]) == ("stale", True, 1)
    assert [(c["kitting_no"], c["from_legacy"], c["has_actuals"]) for c in item["candidates"]] == [(NEW, True, False)]


def test_several_candidates_are_shown_with_their_count(client, admin, fake_clock):
    complete_k1(client, fake_clock)
    other = "0722-1-S-251014-10"
    insert_plan(admin["db"], kitting_no=other, file_no="0722")
    reissue(admin, replacement=None)
    set_stale(admin["db"], K1, "L001", "stale", replacement=None, count=2)  # 既存アプリの判定では候補が2つ(値は入らない)
    sync_plans(admin["app"])
    item = pending(client)["items"][0]
    assert item["replacement_count"] == 2
    assert {c["kitting_no"] for c in item["candidates"]} == {NEW, other}  # 同じロット・ファイルNo.・回の有効な計画も候補に出す


def test_nothing_is_moved_automatically(client, admin, fake_clock):
    complete_k1(client, fake_clock)
    reissue(admin)
    assert count_rows(RunEvent, kitting_no=NEW) == 0 and count_rows(RunEvent, kitting_no=K1) > 0
    assert count_rows(KittingHandover) == 0


def test_confirm_moves_actuals_and_completion_and_cancels_old_plan(client, admin, fake_clock):
    ok(client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": admin["yamada"]}))
    complete_k1(client, fake_clock)
    with new_session() as s:  # 備考と書き出し済みの CSV(食い違いの警告の確認用)
        s.add(RunInput(kitting_no=K1, kind="remark", value="メモ", entered_by=admin["yamada"], entered_at=clock.now(), request_id="r1"))
        s.add(ActualsExport(exported_at=clock.now(), exported_by=admin["yamada"], row_count=1, file_name="a.csv",
                            date_from=clock.now().date(), date_to=clock.now().date(), line_code=None, content=f"{K1},L001"))
        s.commit()
    completion_before = count_rows(RunCompletion, kitting_no=K1)
    reissue(admin)

    r = ok(confirm(client))

    assert r["moved"]["run_events"] == 2 and r["moved"]["run_completions"] == completion_before and r["moved"]["run_inputs"] == 1
    assert any("書き出し済みの CSV" in w for w in r["warnings"])
    assert count_rows(RunEvent, kitting_no=K1) == 0 and count_rows(RunEvent, kitting_no=NEW) == 2  # 消さずに付け替える
    with new_session() as s:
        done = s.get(RunCompletion, 1) or s.query(RunCompletion).filter_by(kitting_no=NEW).first()
        assert done is not None and done.takt_sec_snapshot == 30 and done.teitori_snapshot == 2  # 完了の写しも、丁取りと目標タクトごと移る
        old = s.get(Plan, (K1, "L001"))
        assert (old.status, old.cancel_reason) == ("cancelled", "carried_over")  # 古い計画に取消の印
        h = s.query(KittingHandover).one()  # 変更前と変更後・確定した管理者・日時が履歴に残る
        assert (h.old_kitting_no, h.new_kitting_no, h.confirmed_at) == (K1, NEW, clock.now())
        assert json.loads(h.moved_json)["run_events"] == 2 and s.get(type(old), (NEW, "L001")).status == "active"
    history = ok(client.get("/api/admin/handovers"))
    assert history["items"] == [] and history["history"][0]["confirmed_by"] == "管理 花子(K0042)"


def test_after_the_move_reports_and_efficiency_use_the_new_number(client, admin, fake_clock):
    ok(client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": admin["yamada"]}))
    complete_k1(client, fake_clock)
    reissue(admin)
    ok(confirm(client))
    login(client)

    board = ok(client.get("/api/lines/S/board", params={"date": DAY}))
    assert [p["plan"]["kitting_no"] for p in board["plans"] if p["events"]] == [NEW]  # 画面は新しいキッティングNo.に実績を出す
    assert board["efficiency"]["included"] == 1 and board["efficiency"]["efficiency"] is not None  # 効率も新しい番号で数える
    daily = ok(client.get("/api/admin/reports/daily", params={"date": DAY, "line_code": "S"}))
    assert {r["kitting_no"] for r in daily["rows"] if r["kind"] == "step"} == {NEW} and daily["produced_total"] == 150
    rows = list(csv.DictReader(io.StringIO(client.get("/api/admin/reports/intervals.csv", params={"from": DAY, "to": DAY}).content.decode("utf-8-sig"))))
    assert {r["キッティングNo."] for r in rows if r["区分"] == "工程"} == {NEW}
    actuals = ok(client.get("/api/admin/actuals", params={"from": DAY, "to": DAY}))
    assert [(r["kitting_no"], r["produced_qty"]) for r in actuals["rows"]] == [(NEW, 150)]  # 書き出しの対象も新しい番号


def test_target_with_actuals_cannot_be_confirmed(client, admin, fake_clock):
    ok(client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": admin["yamada"]}))
    complete_k1(client, fake_clock)
    reissue(admin)
    ok(start(client, "setup", kitting_no=NEW))  # 移す先にすでに実績がある
    r = confirm(client)
    assert r.status_code == 409 and "すでに実績があります" in r.json()["detail"]
    assert count_rows(RunEvent, kitting_no=K1) == 2 and count_rows(KittingHandover) == 0  # 何も動かない


def test_only_listed_candidates_and_only_once(client, admin, fake_clock):
    complete_k1(client, fake_clock)
    reissue(admin)
    assert confirm(client, new=K2).status_code == 409  # 候補にない(別の回の計画)
    assert confirm(client, old="no-such").status_code == 404
    ok(confirm(client))
    assert confirm(client).status_code == 404  # 同じ計画を二度移さない


def test_cancelled_plan_with_actuals_is_listed_too(client, admin, fake_clock):
    complete_k1(client, fake_clock)
    insert_plan(admin["db"], kitting_no=NEW, file_no="0722")
    from legacy_fixture import deactivate

    deactivate(admin["db"], K1)  # 既存アプリから読めなくなった(計画を出し直した)
    sync_plans(admin["app"])
    with get_sessionmaker()() as s:
        assert s.get(Plan, (K1, "L001")).cancel_reason == "vanished"
    item = pending(client)["items"][0]
    assert (item["kitting_no"], item["reason"], [c["kitting_no"] for c in item["candidates"]]) == (K1, "vanished", [NEW])
