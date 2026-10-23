"""実績の書き出し(既存アプリに戻すための CSV): 行の単位、割り振り、合計の確かめ、取り消しの除外、面1と面2のひも付け、権限。"""

import csv
import io

import pytest

from app.core.config import get_config
from app.db.models import ActualsExport, Operator, RunEvent
from app.services import admin_auth, masters
from legacy_fixture import insert_plan
from records_helpers import K1, K2, count_rows, end, new_session, ok, reason_id, rid, set_operator, start, sync_plans, void

H = {"X-Genba-Admin": "1"}
URL = "/api/admin/actuals"
DAY = {"from": "2026-10-21", "to": "2026-10-21"}
BODY = {"date_from": "2026-10-21", "date_to": "2026-10-21"}
K3 = "0800-1-S-251014-03"  # 面1だけ(面2の計画が無い)
K4 = "0900-1-S-251014-04"  # 面1・2ロット(A 100、B 50)


def login(client):
    r = client.post("/api/admin/login", json={"worker_id": "K0042", "password": "right-pass-1"}, headers=H)
    assert r.status_code == 200


@pytest.fixture
def admin(client, world, tmp_path, fake_clock):
    """管理者 K0042、今の担当者は作業者ID Y100 の鈴木。書き出し先は tmp_path/exchange。時計は 10/21 9:00(稼働日 10/21)。"""
    cfg = tmp_path / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + f'exchange_dir = "{(tmp_path / "exchange").as_posix()}"\n', encoding="utf-8")
    get_config.cache_clear()
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", "right-pass-1")
        suzuki = masters.add_operator(s, "鈴木", worker_id="Y100").id
    set_operator(client, suzuki)
    fake_clock.advance(hours=1)
    return {**world, "suzuki": suzuki, "exchange": tmp_path / "exchange"}


def produce(client, fake_clock, kitting_no, *qtys):
    for i, q in enumerate(qtys):
        extra = {"restart_reason_id": reason_id("人員交代")} if i else {}
        ok(start(client, "production", kitting_no=kitting_no, **extra))
        fake_clock.advance(minutes=10)
        ok(end(client, "production", kitting_no=kitting_no, produced_qty=q))


def finish(client, fake_clock, kitting_no):
    ok(start(client, "cleanup", kitting_no=kitting_no))
    fake_clock.advance(minutes=5)
    ok(end(client, "cleanup", kitting_no=kitting_no))


def ng(client, kitting_no, lot_no, side, qty):
    ok(client.put(f"/api/runs/{kitting_no}/ng-qty", json={"request_id": rid(), "lot_no": lot_no, "side": side, "ng_qty": qty}))


def listing(client, **params):
    login(client)
    r = client.get(URL, params={**DAY, **params})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def by_key(rows):
    return {(r["kitting_no"], r["lot_no"]): r for r in rows}


def export(client, **body):
    login(client)
    return client.post(f"{URL}/export", json={**BODY, **body}, headers=H)


# --- 行の単位(面1と面2) ---

def test_side2_row_carries_both_sides_and_side1_row_is_not_shown(client, admin, fake_clock):
    produce(client, fake_clock, K1, 300)
    ng(client, K1, "L001", 1, 5)
    finish(client, fake_clock, K1)
    produce(client, fake_clock, K2, 200, 90)
    ng(client, K2, "L001", 2, 3)
    finish(client, fake_clock, K2)
    rows = listing(client)
    assert [(r["kitting_no"], r["side"]) for r in rows] == [(K2, 2)]
    r = rows[0]
    assert (r["produced_qty"], r["ng_side1"], r["ng_side2"], r["side1_kitting_no"]) == (290, 5, 3, K1)
    assert (r["worker_id"], r["completed_on"], r["source_db"], r["exportable"]) == ("Y100", "2026-10-21", "2026-10", True)


def test_side1_only_lot_shows_the_side1_row(client, admin, fake_clock):
    insert_plan(admin["db"], kitting_no=K3, lot_no="L010", file_no="0800", qty=120)
    sync_plans(admin["app"])
    produce(client, fake_clock, K3, 120)
    ng(client, K3, "L010", 1, 2)
    finish(client, fake_clock, K3)
    r = by_key(listing(client))[(K3, "L010")]
    assert (r["side"], r["produced_qty"], r["ng_side1"], r["ng_side2"], r["exportable"]) == (1, 120, 2, 0, True)


def test_side1_row_waits_while_a_side2_plan_exists(client, admin, fake_clock):
    produce(client, fake_clock, K1, 300)
    finish(client, fake_clock, K1)
    assert listing(client) == []  # 面2(K2)の完了の行にまとめるので、面1の行は出さない


def test_side1_ng_entered_on_the_side2_screen_is_used(client, admin, fake_clock):
    produce(client, fake_clock, K2, 300)
    ng(client, K2, "L001", 1, 7)  # 面2の画面から面1のNG
    finish(client, fake_clock, K2)
    r = listing(client)[0]
    assert (r["ng_side1"], r["ng_side2"]) == (7, 0)
    assert any("面1の計画" in n and "完了していません" in n for n in r["notes"])


def test_ambiguous_pairing_is_warned_and_not_exported(client, admin, fake_clock):
    insert_plan(admin["db"], kitting_no="0722-1-S-251015-01", lot_no="L001", qty=100)  # 同じロット・ファイルNo.の面1が2つ
    sync_plans(admin["app"])
    produce(client, fake_clock, K2, 300)
    finish(client, fake_clock, K2)
    r = listing(client)[0]
    assert r["exportable"] is False and r["side1_kitting_no"] is None
    assert "ひも付けが決まりません(面1の計画 2件、面2の計画 1件)" in r["warnings"][0]
    res = export(client)
    assert res.status_code == 409 and "書き出せる行がありません" in res.json()["detail"]


def test_missing_worker_id_is_warned(client, admin, fake_clock):
    set_operator(client, admin["yamada"])  # 作業者IDの無い作業者
    produce(client, fake_clock, K2, 300)
    finish(client, fake_clock, K2)
    r = listing(client)[0]
    assert r["exportable"] is False and r["warnings"] == ["片付けを終えた人の作業者IDがありません"]


# --- 生産数(累計・取り消しの除外・割り振り) ---

def test_voided_production_is_not_counted(client, admin, fake_clock):
    produce(client, fake_clock, K2, 200, 50)
    with new_session() as s:
        last = s.query(RunEvent).filter_by(kitting_no=K2, step_type="production", seq=2).one()
    ok(void(client, last.id, kitting_no=K2))
    finish(client, fake_clock, K2)
    assert listing(client)[0]["produced_qty"] == 200


@pytest.fixture
def two_lots(client, admin, fake_clock):
    for lot, qty in (("A", 100), ("B", 50)):
        insert_plan(admin["db"], kitting_no=K4, lot_no=lot, file_no="0900", qty=qty)
    sync_plans(admin["app"])
    produce(client, fake_clock, K4, 160)
    finish(client, fake_clock, K4)
    return admin


def test_total_is_allocated_to_lots_in_order(client, two_lots):
    rows = by_key(listing(client))
    assert (rows[(K4, "A")]["produced_qty"], rows[(K4, "B")]["produced_qty"]) == (100, 60)
    assert rows[(K4, "A")]["kitting_produced_total"] == 160


def test_edited_quantities_must_add_up(client, two_lots):
    r = export(client, quantities=[{"kitting_no": K4, "lot_no": "A", "produced_qty": 90}])
    assert r.status_code == 409
    assert r.json()["detail"] == f"キッティングNo. {K4} のロットの生産数の合計(150)が、記録の累計(160)と一致しません。ロットの数を直してください"
    assert count_rows(ActualsExport) == 0


def test_unknown_row_is_rejected(client, two_lots):
    r = export(client, quantities=[{"kitting_no": K4, "lot_no": "Z", "produced_qty": 1}])
    assert r.status_code == 409 and "一覧に無い行です" in r.json()["detail"]


# --- CSV と履歴 ---

def _csv_rows(data: bytes):
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" in data
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))


def test_export_writes_csv_and_history_without_changing_records(client, two_lots, fake_clock):
    events_before = count_rows(RunEvent)
    body = {"quantities": [{"kitting_no": K4, "lot_no": "A", "produced_qty": 90},
                           {"kitting_no": K4, "lot_no": "B", "produced_qty": 70}]}
    first = ok(export(client, **body))
    assert first["row_count"] == 2 and first["exported_by"] == "管理 花子(K0042)"
    assert first["file_name"].startswith("actuals_20261021_") and first["file_name"].endswith(f"_{first['id']:04d}.csv")
    saved = two_lots["exchange"] / "actuals" / first["file_name"]
    rows = _csv_rows(saved.read_bytes())
    assert rows[0] == ["書式版", "書き出し日時", "元のDB(フォルダ名)", "キッティングNo.", "ロットNo.", "ファイルNo.", "面", "日付", "生産数(累計)",
                       "NG面1", "NG面2", "担当者ID"]
    assert all(r[0] == "1" for r in rows[1:]) and len(rows[0]) == 12
    assert [r[2:] for r in rows[1:]] == [
        ["2026-10", K4, "A", "0900", "1", "2026-10-21", "90", "0", "0", "Y100"],
        ["2026-10", K4, "B", "0900", "1", "2026-10-21", "70", "0", "0", "Y100"],
    ]
    assert not list((two_lots["exchange"] / "actuals").glob("*.tmp"))

    fake_clock.advance(seconds=5)
    second = ok(export(client, **body))
    assert second["id"] != first["id"] and count_rows(ActualsExport) == 2
    assert count_rows(RunEvent) == events_before  # 実績の記録は変わらない
    assert listing(client)[0]["produced_qty"] == 100  # 直した数は保存しない(一覧は割り振りのまま)

    history = ok(client.get(f"{URL}/exports"))
    assert [h["id"] for h in history] == [second["id"], first["id"]]
    download = client.get(f"{URL}/exports/{first['id']}/file")
    assert download.status_code == 200 and download.content == saved.read_bytes()
    assert first["file_name"] in download.headers["content-disposition"]


def test_period_and_line_filters(client, two_lots):
    assert listing(client, line_code="s") != []  # ラインの記号は正規化して探す
    login(client)
    assert client.get(URL, params={"from": "2026-10-22", "to": "2026-10-22"}).json()["rows"] == []
    r = client.get(URL, params={"from": "2026-10-22", "to": "2026-10-21"})
    assert r.status_code == 409


# --- 権限 ---

def test_requires_admin_login_and_header(client, two_lots):
    assert client.get(URL, params=DAY).status_code == 401
    assert client.post(f"{URL}/export", json=BODY, headers=H).status_code == 401
    assert client.get(f"{URL}/exports").status_code == 401
    login(client)
    assert client.post(f"{URL}/export", json=BODY).status_code == 403  # 決まったヘッダーが無い
    with new_session() as s:
        s.query(Operator).filter_by(worker_id="K0042").update({"role": "operator"})
        s.commit()
    assert client.get(URL, params=DAY).status_code == 401  # 管理者でなくなった
    assert count_rows(ActualsExport) == 0


def test_save_failure_leaves_no_history(client, two_lots):
    two_lots["exchange"].write_text("フォルダではない", encoding="utf-8")  # 書き出し先を作れない
    r = export(client)
    assert r.status_code == 409 and "書き出し先に保存できませんでした" in r.json()["detail"]
    assert count_rows(ActualsExport) == 0


def test_worker_id_is_exported_as_written_in_the_legacy_app(client, admin, fake_clock):
    with new_session() as s:
        tanaka = masters.add_operator(s, "田中", worker_id="ｔ０１").id  # 既存アプリの表記(全角・小文字)のまま持つ
    set_operator(client, tanaka)
    produce(client, fake_clock, K2, 300)
    finish(client, fake_clock, K2)
    assert listing(client)[0]["worker_id"] == "ｔ０１"  # 正規化した値(T01)ではなく、workers の worker_id と同じもの
