"""今の担当者・工程の記録・NG数と備考・完了・付帯作業・ライン画面用の取得のAPI(開発指針 5.4〜5.7)。"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.models import ApiRequest, Equipment, Line, LineOperator, Reason, RunCompletion, RunEvent, RunInput
from app.db.session import get_sessionmaker
from app.services import masters
from app.services.plan_sync import run_plan_sync
from legacy_fixture import deactivate, insert_plan

K1 = "0722-1-S-251014-01"
K2 = "0722-2-S-251014-02"
LOT = "L001"


def rid() -> str:
    return uuid.uuid4().hex


@pytest.fixture
def client(tmp_path, monkeypatch, fake_clock):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "api.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_config.cache_clear()


def _session():
    return get_sessionmaker()()


def _sync(legacy_app):
    with _session() as s:
        r = run_plan_sync(s, legacy_app)
    assert r.result == "ok"
    return r


def _count(model, **where) -> int:
    with _session() as s:
        stmt = select(func.count()).select_from(model)
        for k, v in where.items():
            stmt = stmt.where(getattr(model, k) == v)
        return s.scalar(stmt)


def _reason_id(name: str) -> int:
    with _session() as s:
        return s.scalars(select(Reason.id).where(Reason.name == name)).one()


@pytest.fixture
def world(client, legacy_app, legacy_db):
    """計画2件(ラインS。K1 は数量300・タクト30秒)、作業者2人(山田・佐藤)。今の担当者は未設定。"""
    insert_plan(legacy_db, kitting_no=K1, qty=300)
    insert_plan(legacy_db, kitting_no=K2, side="2", qty=300, start="2026/10/21 13:00:00", end="2026/10/21 15:00:00")
    _sync(legacy_app)
    with _session() as s:
        yamada = masters.add_operator(s, "山田").id
        sato = masters.add_operator(s, "佐藤").id
    return {"yamada": yamada, "sato": sato, "app": legacy_app, "db": legacy_db}


def set_operator(client, operator_id, line="S"):
    r = client.put(f"/api/lines/{line}/operator", json={"request_id": rid(), "operator_id": operator_id})
    assert r.status_code == 200, r.text
    return r.json()


def start(client, step, kitting_no=K1, lot_no=LOT, **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/runs/{kitting_no}/{lot_no}/steps/{step}/start", json=body)


def end(client, step, kitting_no=K1, lot_no=LOT, **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/runs/{kitting_no}/{lot_no}/steps/{step}/end", json=body)


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def conflict(r, text):
    assert r.status_code == 409, r.text
    assert text in r.json()["detail"]
    return r.json()["detail"]


# --- 今の担当者 ---


def test_current_operator_change(client, world, fake_clock):
    assert client.get("/api/lines/S/operator").json() is None

    first = set_operator(client, world["yamada"])
    assert (first["operator_id"], first["operator_name"]) == (world["yamada"], "山田")
    assert first["start_at"] == "2026-10-21T08:00:00+09:00"

    fake_clock.advance(hours=2)
    set_operator(client, world["sato"])

    now = client.get("/api/lines/S/operator").json()
    assert now["operator_name"] == "佐藤" and now["start_at"] == "2026-10-21T10:00:00+09:00"
    with _session() as s:  # 交代すると前の行に end_at が入る(行は消さない)
        rows = list(s.scalars(select(LineOperator).order_by(LineOperator.id)))
    assert [(r.operator_id, r.end_at is not None) for r in rows] == [(world["yamada"], True), (world["sato"], False)]


def test_operator_change_rules(client, world):
    conflict(client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": 999}), "作業者(ID 999)が見つかりません")
    r = client.put("/api/lines/X/operator", json={"request_id": rid(), "operator_id": world["yamada"]})
    assert r.status_code == 404 and "ライン「X」が見つかりません" in r.json()["detail"]
    # ラインの記号は正規化して探す(s → S)
    assert client.get("/api/lines/s/operator").status_code == 200


def test_same_operator_again_does_not_add_row(client, world):
    set_operator(client, world["yamada"])
    set_operator(client, world["yamada"])
    assert _count(LineOperator) == 1


# --- 工程: 記録者 ---


def test_start_without_operator_is_rejected(client, world):
    conflict(start(client, "setup"), "担当者が設定されていません")
    assert _count(RunEvent) == 0


def test_explicit_operator_is_used_without_current(client, world):
    e = ok(start(client, "setup", operator_id=world["sato"]))["event"]
    assert e["started_by"] == world["sato"] and e["started_by_name"] == "佐藤"


def test_operator_change_between_start_and_end(client, world, fake_clock):
    set_operator(client, world["yamada"])
    ok(start(client, "production"))
    fake_clock.advance(minutes=30)
    set_operator(client, world["sato"])  # 人員交代
    fake_clock.advance(minutes=30)
    e = ok(end(client, "production", produced_qty=120))["event"]

    assert (e["started_by_name"], e["ended_by_name"]) == ("山田", "佐藤")
    assert e["start_at"] == "2026-10-21T08:00:00+09:00" and e["end_at"] == "2026-10-21T09:00:00+09:00"


def test_one_time_operator_override(client, world):
    set_operator(client, world["yamada"])
    e = ok(start(client, "setup", operator_id=world["sato"]))["event"]  # 1回の操作だけ別の人
    assert e["started_by_name"] == "佐藤"
    assert client.get("/api/lines/S/operator").json()["operator_name"] == "山田"


# --- 工程: ルール ---


@pytest.fixture
def staffed(client, world):
    set_operator(client, world["yamada"])
    return world


def test_unknown_plan_is_404(client, staffed):
    r = start(client, "setup", kitting_no="9999-1-S-251014-99")
    assert r.status_code == 404 and "計画" in r.json()["detail"]


def test_unknown_step_type_is_422(client, staffed):
    assert start(client, "lunch").status_code == 422


def test_cancelled_plan_cannot_start_but_can_end(client, staffed):
    ok(start(client, "setup"))
    deactivate(staffed["db"], K1)  # 既存側で消えた → 取消
    _sync(staffed["app"])

    conflict(start(client, "n1_check"), "取消になった計画は開始できません")
    ok(end(client, "setup"))


def test_double_start_is_rejected(client, staffed):
    ok(start(client, "setup"))
    conflict(start(client, "setup"), "段取りは開始されたまま終了していません")
    assert _count(RunEvent) == 1


def test_end_without_start_is_rejected(client, staffed):
    conflict(end(client, "first_article"), "初品チェックは開始されていません")
    ok(start(client, "first_article"))
    ok(end(client, "first_article"))
    conflict(end(client, "first_article"), "初品チェックは開始されていません")  # 終了済み


def test_production_end_requires_qty(client, staffed):
    ok(start(client, "production"))
    conflict(end(client, "production"), "生産数を入力してください")
    conflict(end(client, "production", produced_qty=-1), "0以上の整数")
    assert end(client, "production", produced_qty=1.5).status_code == 422  # 整数でない
    e = ok(end(client, "production", produced_qty=0))["event"]  # 0 はよい
    assert e["produced_qty"] == 0


def test_other_steps_reject_qty(client, staffed):
    ok(start(client, "setup"))
    conflict(end(client, "setup", produced_qty=10), "段取りの終了では、生産数は受け付けません")


def test_restart_reason_rules(client, staffed):
    conflict(start(client, "production", restart_reason_id=_reason_id("人員交代")), "1回目の生産の開始では、再開理由は受け付けません")
    conflict(start(client, "setup", restart_reason_id=_reason_id("人員交代")), "段取りの開始では、再開理由は受け付けません")

    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    conflict(start(client, "production"), "再開理由を選んでください")
    conflict(start(client, "production", restart_reason_id=_reason_id("立上立会")), "生産の再開理由として使えません")
    conflict(start(client, "production", restart_reason_id=999), "生産の再開理由として使えません")

    e = ok(start(client, "production", restart_reason_id=_reason_id("人員交代")))["event"]
    assert (e["seq"], e["restart_reason_name"]) == (2, "人員交代")


def test_restart_equipment_rules(client, staffed, equipment):
    machine = _reason_id("マシントラブル")
    conflict(start(client, "production", equipment_id=equipment["own"]), "設備は、設備が必要な再開理由")  # 1回目
    conflict(start(client, "setup", equipment_id=equipment["own"]), "設備は、設備が必要な再開理由")  # ほかの工程
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=10))

    conflict(start(client, "production", restart_reason_id=_reason_id("人員交代"), equipment_id=equipment["own"]),
             "設備は、設備が必要な再開理由")
    conflict(start(client, "production", restart_reason_id=machine, equipment_id=equipment["other"]),
             "このラインの設備ではありません")
    conflict(start(client, "production", restart_reason_id=machine, equipment_id=999), "このラインの設備ではありません")

    e = ok(start(client, "production", restart_reason_id=machine, equipment_id=equipment["own"]))["event"]
    assert (e["equipment_id"], e["equipment_name"]) == (equipment["own"], "マウンター1")
    ok(end(client, "production", produced_qty=10))

    # 設備は任意(設備が必要な再開理由でも、選ばなくてよい)
    e = ok(start(client, "production", restart_reason_id=machine))["event"]
    assert e["equipment_id"] is None and e["equipment_name"] is None
    ok(end(client, "production", produced_qty=10))

    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert [x["equipment_name"] for x in plan["events"]] == [None, "マウンター1", None]


def test_restart_equipment_is_part_of_request_content(client, staffed, equipment):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=10))
    request_id = rid()
    body = {"request_id": request_id, "restart_reason_id": _reason_id("マシントラブル")}
    first = ok(start(client, "production", equipment_id=equipment["own"], **body))
    assert ok(start(client, "production", equipment_id=equipment["own"], **body)) == first
    conflict(start(client, "production", **body), "同じリクエストIDで")  # 設備の有無が違う


def test_different_steps_may_overlap(client, staffed):
    ok(start(client, "production"))
    ok(start(client, "first_article"))  # 生産中に初品チェック
    ok(start(client, "xray"))
    ok(end(client, "first_article"))
    ok(end(client, "production", produced_qty=50))
    assert _count(RunEvent) == 3


def test_more_than_three_production_segments(client, staffed):
    reason = _reason_id("トラブル停止")
    for i in range(5):  # 記録用紙は3欄だが、データ上は上限なし
        ok(start(client, "production", restart_reason_id=reason if i else None))
        ok(end(client, "production", produced_qty=10))
    with _session() as s:
        seqs = list(s.scalars(select(RunEvent.seq).where(RunEvent.step_type == "production").order_by(RunEvent.seq)))
    assert seqs == [1, 2, 3, 4, 5]


def test_setup_can_be_redone(client, staffed):
    ok(start(client, "setup"))
    ok(end(client, "setup"))
    e = ok(start(client, "setup"))["event"]  # トラブルで別の計画に切り替え、戻ってから段取りをやり直す
    assert e["seq"] == 2
    ok(end(client, "setup"))


def test_seq_is_per_plan_and_step(client, staffed):
    ok(start(client, "setup"))
    assert ok(start(client, "setup", kitting_no=K2))["event"]["seq"] == 1
    assert ok(start(client, "n1_check"))["event"]["seq"] == 1


# --- 冪等性 ---


def test_resend_returns_first_result(client, staffed, fake_clock):
    request_id = rid()
    first = ok(start(client, "setup", request_id=request_id))
    fake_clock.advance(minutes=5)
    again = ok(start(client, "setup", request_id=request_id))

    assert again == first  # 最初の結果をそのまま返す
    assert _count(RunEvent) == 1

    end_id = rid()
    ended = ok(end(client, "setup", request_id=end_id))
    assert ok(end(client, "setup", request_id=end_id)) == ended  # 終了の再送も同じ
    assert ok(start(client, "setup", request_id=request_id)) == first  # 状態が変わっても、最初の結果
    assert _count(RunEvent) == 1


def test_same_request_id_with_different_content_is_rejected(client, staffed):
    request_id = rid()
    ok(start(client, "setup", request_id=request_id))
    conflict(start(client, "n1_check", request_id=request_id), "同じリクエストIDで、内容の異なる操作")
    conflict(start(client, "setup", kitting_no=K2, request_id=request_id), "同じリクエストIDで")
    conflict(end(client, "setup", request_id=request_id), "同じリクエストIDで")  # 別の操作に使い回した
    assert _count(RunEvent) == 1


def test_failed_request_can_be_retried_with_same_id(client, world):
    request_id = rid()
    conflict(start(client, "setup", request_id=request_id), "担当者が設定されていません")
    set_operator(client, world["yamada"])
    ok(start(client, "setup", request_id=request_id))  # 失敗した操作は記録しないので、同じIDで送り直せる
    assert _count(ApiRequest, request_id=request_id) == 1


def test_operator_change_is_idempotent(client, world):
    request_id = rid()
    body = {"request_id": request_id, "operator_id": world["yamada"]}
    first = ok(client.put("/api/lines/S/operator", json=body))
    assert ok(client.put("/api/lines/S/operator", json=body)) == first
    conflict(client.put("/api/lines/S/operator", json={**body, "operator_id": world["sato"]}), "同じリクエストIDで")
    assert _count(LineOperator) == 1


# --- NG数・備考 ---


def test_ng_qty_latest_is_effective(client, staffed):
    ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 3}))
    r = ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 5}))
    assert (r["kind"], r["value"], r["entered_by_name"]) == ("ng_qty", "5", "山田")
    assert r["entered_at"].endswith("+09:00")
    assert _count(RunInput, kind="ng_qty") == 2  # 行を追加する(上書きしない)
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["ng_qty"] == 5


def test_ng_qty_rules(client, world):
    conflict(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 1}), "担当者が設定されていません")
    set_operator(client, world["yamada"])
    conflict(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": -1}), "0以上の整数")
    assert client.put(f"/api/runs/X/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 1}).status_code == 404

    body = {"request_id": rid(), "ng_qty": 2}
    first = ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json=body))
    assert ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json=body)) == first
    assert _count(RunInput) == 1


def test_remarks(client, staffed):
    conflict(client.post(f"/api/runs/{K1}/{LOT}/remarks", json={"request_id": rid(), "text": "  "}), "備考が空です")
    r = ok(client.post(f"/api/runs/{K1}/{LOT}/remarks", json={"request_id": rid(), "text": " 部品の向きに注意 ", "operator_id": staffed["sato"]}))
    assert (r["kind"], r["value"], r["entered_by_name"]) == ("remark", "部品の向きに注意", "佐藤")


# --- 完了 ---


def test_cleanup_end_completes_with_snapshots(client, staffed):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    ok(start(client, "production", restart_reason_id=_reason_id("人員交代")))
    ok(end(client, "production", produced_qty=150))
    ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 3}))
    ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 5}))
    ok(start(client, "cleanup"))

    r = ok(end(client, "cleanup"))

    c = r["completion"]
    assert (c["produced_qty"], c["ng_qty"], c["plan_qty_snapshot"], c["takt_sec_snapshot"]) == (250, 5, 300, 30.0)
    assert c["utilization"] is None and c["completed_at"] == r["event"]["end_at"]

    # あとで計画の数量が変わっても、完了の写しは変わらない
    insert_plan(staffed["db"], kitting_no=K1, qty=400, at="2026-10-21 09:00:00")
    _sync(staffed["app"])
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["plan"]["planned_qty"] == 400
    assert plan["completed"] is True and plan["completion"]["plan_qty_snapshot"] == 300


def test_other_steps_do_not_complete(client, staffed):
    ok(start(client, "setup"))
    assert ok(end(client, "setup"))["completion"] is None
    assert _count(RunCompletion) == 0


def test_cleanup_again_adds_completion_and_latest_wins(client, staffed, fake_clock):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    ok(start(client, "cleanup"))
    ok(end(client, "cleanup"))

    # 完了後も工程の記録は受け付ける
    ok(start(client, "production", restart_reason_id=_reason_id("計画切替")))
    ok(end(client, "production", produced_qty=20))
    fake_clock.advance(minutes=10)
    ok(start(client, "cleanup"))
    second = ok(end(client, "cleanup"))["completion"]

    assert second["produced_qty"] == 120
    assert _count(RunCompletion) == 2
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["completion"]["id"] == second["id"]


def test_completion_resend_does_not_duplicate(client, staffed):
    ok(start(client, "cleanup"))
    request_id = rid()
    first = ok(end(client, "cleanup", request_id=request_id))
    assert ok(end(client, "cleanup", request_id=request_id)) == first
    assert _count(RunCompletion) == 1


# --- 付帯作業 ---


@pytest.fixture
def equipment(staffed):
    with _session() as s:
        s.add(Line(line_code="T", name="Tライン", active=True, sort_order=99))
        s.commit()
        own = masters.add_equipment(s, "S", "マウンター1").id
        other = masters.add_equipment(s, "T", "マウンター9").id
    return {"own": own, "other": other}


def ev_start(client, line="S", **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/lines/{line}/events/start", json=body)


def ev_end(client, event_id, line="S", **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/lines/{line}/events/{event_id}/end", json=body)


def test_line_event_reason_rules(client, staffed, equipment):
    conflict(ev_start(client, reason_id=_reason_id("人員交代")), "付帯作業として使えません")
    conflict(ev_start(client, reason_id=999), "付帯作業として使えません")
    conflict(ev_start(client, reason_id=_reason_id("マシントラブル")), "マシントラブルでは、設備を選んでください")
    conflict(ev_start(client, reason_id=_reason_id("マシントラブル"), equipment_id=equipment["other"]), "このラインの設備ではありません")
    conflict(ev_start(client, reason_id=_reason_id("その他トラブル")), "その他トラブルでは、理由を記入してください")
    conflict(ev_start(client, reason_id=_reason_id("その他トラブル"), reason_text="  "), "理由を記入してください")

    e = ok(ev_start(client, reason_id=_reason_id("マシントラブル"), equipment_id=equipment["own"]))
    assert (e["reason_name"], e["equipment_name"], e["started_by_name"]) == ("マシントラブル", "マウンター1", "山田")
    t = ok(ev_start(client, reason_id=_reason_id("その他トラブル"), reason_text="エア漏れ"))
    assert t["reason_text"] == "エア漏れ"


def test_line_event_overlap_rules(client, staffed):
    first = ok(ev_start(client, reason_id=_reason_id("部品探し")))
    conflict(ev_start(client, reason_id=_reason_id("部品探し")), "部品探しは開始されたまま終了していません")
    ok(ev_start(client, reason_id=_reason_id("欠品")))  # 異なる理由どうしは重なってよい

    ended = ok(ev_end(client, first["id"], operator_id=staffed["sato"]))
    assert ended["end_at"] is not None and ended["ended_by_name"] == "佐藤"
    conflict(ev_end(client, first["id"]), "すでに終了しています")
    ok(ev_start(client, reason_id=_reason_id("部品探し")))  # 終了したら、同じ理由をまた開始できる


def test_line_event_end_not_found(client, staffed):
    assert ev_end(client, 999).status_code == 404
    e = ok(ev_start(client, reason_id=_reason_id("欠品")))
    with _session() as s:
        s.add(Line(line_code="T", name="Tライン", active=True, sort_order=99))
        s.commit()
    assert ev_end(client, e["id"], line="T").status_code == 404  # 別のラインの付帯作業


def test_line_event_requires_operator(client, world):
    conflict(ev_start(client, reason_id=_reason_id("欠品")), "担当者が設定されていません")


def test_line_event_idempotent(client, staffed):
    request_id = rid()
    first = ok(ev_start(client, reason_id=_reason_id("欠品"), request_id=request_id))
    assert ok(ev_start(client, reason_id=_reason_id("欠品"), request_id=request_id)) == first
    conflict(ev_start(client, reason_id=_reason_id("部品探し"), request_id=request_id), "同じリクエストIDで")

    end_id = rid()
    ended = ok(ev_end(client, first["id"], request_id=end_id))
    assert ok(ev_end(client, first["id"], request_id=end_id)) == ended


# --- ライン画面用の取得 ---


def test_board(client, staffed, fake_clock):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=150))
    ok(start(client, "production", kitting_no=K2))
    ok(end(client, "production", kitting_no=K2, produced_qty=60))
    ok(start(client, "production", kitting_no=K2, restart_reason_id=_reason_id("人員交代")))  # 終了していない区切りは数えない
    ev = ok(ev_start(client, reason_id=_reason_id("欠品")))

    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))

    assert b["line_code"] == "S" and b["date"] == "2026-10-21"
    assert b["current_operator"]["operator_name"] == "山田"
    assert [p["plan"]["kitting_no"] for p in b["plans"]] == [K1, K2]
    p1, p2 = b["plans"]
    assert (p1["produced_qty"], p1["progress"], p1["completed"], p1["ng_qty"]) == (150, 0.5, False, None)
    assert (p2["produced_qty"], p2["progress"]) == (60, 0.2)
    assert [e["seq"] for e in p2["events"]] == [1, 2]
    assert b["line_progress"] == pytest.approx(210 / 600)
    assert b["utilization"] is None
    assert [e["id"] for e in b["line_events"]] == [ev["id"]]
    for t in (p1["events"][0]["start_at"], p1["events"][0]["end_at"], b["current_operator"]["start_at"], b["line_events"][0]["start_at"]):
        assert t.endswith("+09:00")

    # 日付を省略すると今日。別の日は計画も付帯作業も出ない
    assert ok(client.get("/api/lines/S/board")) == b
    other = ok(client.get("/api/lines/S/board", params={"date": "2026-10-23"}))
    assert other["plans"] == [] and other["line_events"] == [] and other["line_progress"] is None


def test_board_with_zero_qty_plan(client, staffed):
    insert_plan(staffed["db"], kitting_no="0800-1-S-251014-03", file_no="0800", qty=0, start="2026/10/21 16:00:00", end="2026/10/21 17:00:00")
    _sync(staffed["app"])
    ok(start(client, "production", kitting_no="0800-1-S-251014-03"))
    ok(end(client, "production", kitting_no="0800-1-S-251014-03", produced_qty=5))

    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))

    zero = b["plans"][-1]
    assert zero["plan"]["planned_qty"] == 0 and zero["progress"] is None  # 計画数が0でも落ちない
    assert b["line_progress"] == pytest.approx(5 / 600)


def test_board_all_zero_qty(client, staffed):
    deactivate(staffed["db"], K1)
    deactivate(staffed["db"], K2)
    insert_plan(staffed["db"], kitting_no="0800-1-S-251014-03", file_no="0800", qty=0)
    _sync(staffed["app"])
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert [p["progress"] for p in b["plans"]] == [None] and b["line_progress"] is None


def test_board_unknown_line(client, world):
    assert client.get("/api/lines/X/board").status_code == 404


def test_board_open_line_event_continues_until_now(client, staffed, fake_clock):
    ev = ok(ev_start(client, reason_id=_reason_id("欠品")))  # 2026-10-21 08:00 に開始し、終了していない
    fake_clock.advance(days=1)  # 翌日になっても続いている
    assert [e["id"] for e in ok(client.get("/api/lines/S/board", params={"date": "2026-10-22"}))["line_events"]] == [ev["id"]]
    assert ok(client.get("/api/lines/S/board", params={"date": "2026-10-23"}))["line_events"] == []  # 今より後の日には出さない


def test_board_line_event_spanning_midnight(client, staffed, fake_clock):
    fake_clock.advance(hours=15)  # 2026-10-21 23:00
    ev = ok(ev_start(client, reason_id=_reason_id("部品探し")))
    fake_clock.advance(hours=2)  # 翌日 01:00
    ok(ev_end(client, ev["id"]))
    for day in ("2026-10-21", "2026-10-22"):
        assert [e["id"] for e in ok(client.get("/api/lines/S/board", params={"date": day}))["line_events"]] == [ev["id"]]


# --- マスタ ---


def test_masters(client, staffed, equipment):
    with _session() as s:
        s.add(Equipment(line_code="S", name="使わない設備", active=False, sort_order=1))
        s.get(Reason, _reason_id("計画切替")).active = False
        s.commit()

    m = ok(client.get("/api/masters"))
    assert [x["line_code"] for x in m["lines"]] == ["S", "T"]
    assert [x["name"] for x in m["operators"]] == ["山田", "佐藤"]
    assert [x["name"] for x in m["equipment"]] == ["マウンター1", "マウンター9"]  # 無効なものは出さない
    assert "計画切替" not in [x["name"] for x in m["reasons"]]
    assert m["reasons"][0]["name"] == "部品探し" and m["reasons"][0]["category"] == "loss"

    assert [x["name"] for x in ok(client.get("/api/masters", params={"line_code": "S"}))["equipment"]] == ["マウンター1"]
    assert client.get("/api/masters", params={"line_code": "X"}).status_code == 404


def test_sync_registers_new_lines(client, world):
    insert_plan(world["db"], kitting_no="0722-1-T-251014-09", line="t")
    _sync(world["app"])
    with _session() as s:
        lines = {line.line_code: line.name for line in s.scalars(select(Line))}
    assert lines == {"S": "Sライン", "T": "Tライン"}


def test_requests_without_request_id_are_rejected(client, staffed):
    r = client.post(f"/api/runs/{K1}/{LOT}/steps/setup/start", json={})
    assert r.status_code == 422
    r = client.post(f"/api/runs/{K1}/{LOT}/steps/setup/start", json={"request_id": rid(), "unknown": 1})
    assert r.status_code == 422  # 知らない項目は受け付けない
