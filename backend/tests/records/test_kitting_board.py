"""board と計画のAPIの、キッティングNo.のまとまりの単位(複数ロット・一部の取消・ロットで違う値)。"""

from sqlalchemy import select

from app.db.models import PlanSyncWarning
from legacy_fixture import deactivate, insert_plan
from records_helpers import conflict, end, new_session, ok, start, sync_plans

MULTI = "1000-1-S-251014-09"


def _add_multi(db, lots=(("LA", 100, "基板A"), ("LB", 200, "基板B")), **kw):
    for lot, qty, board in lots:
        insert_plan(db, kitting_no=MULTI, lot_no=lot, file_no="1000", qty=qty, board=board,
                    start=kw.get("start", "2026/10/21 16:00:00"), end="2026/10/21 18:00:00")


def _board_plan(client, kitting_no=MULTI):
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    return next((p for p in b["plans"] if p["plan"]["kitting_no"] == kitting_no), None)


def test_one_frame_per_kitting_with_lots(client, staffed):
    _add_multi(staffed["db"])
    sync_plans(staffed["app"])
    ok(start(client, "production", kitting_no=MULTI))
    ok(end(client, "production", kitting_no=MULTI, produced_qty=150))

    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert [p["plan"]["kitting_no"] for p in b["plans"]].count(MULTI) == 1  # ロットが2つでも枠は1つ
    p = _board_plan(client)
    assert p["plan"]["lots"] == [
        {"lot_no": "LA", "product_name": "基板A", "planned_qty": 100},
        {"lot_no": "LB", "product_name": "基板B", "planned_qty": 200},
    ]
    assert (p["plan"]["planned_qty"], p["produced_qty"]) == (300, 150)
    # 計画の一覧(稼働日)もまとまりの単位
    listed = ok(client.get("/api/lines/S/plans", params={"date": "2026-10-21"}))
    assert [x["kitting_no"] for x in listed].count(MULTI) == 1


def test_partly_cancelled_uses_remaining_lots(client, staffed):
    _add_multi(staffed["db"])
    sync_plans(staffed["app"])
    deactivate(staffed["db"], MULTI, "LB")
    sync_plans(staffed["app"])
    p = _board_plan(client)
    assert [lot["lot_no"] for lot in p["plan"]["lots"]] == ["LA"] and p["plan"]["planned_qty"] == 100


def test_all_lots_cancelled(client, staffed):
    _add_multi(staffed["db"])
    sync_plans(staffed["app"])
    deactivate(staffed["db"], MULTI, "LA")
    deactivate(staffed["db"], MULTI, "LB")
    sync_plans(staffed["app"])
    assert _board_plan(client) is None
    r = ok(client.get(f"/api/runs/{MULTI}"))
    assert r["plan"]["status"] == "cancelled" and len(r["plan"]["lots"]) == 2
    conflict(start(client, "setup", kitting_no=MULTI), "取消になった計画は開始できません")


def test_differing_values_warn(client, staffed):
    insert_plan(staffed["db"], kitting_no=MULTI, lot_no="LA", file_no="1000", start="2026/10/21 16:00:00", end="2026/10/21 18:00:00")
    insert_plan(staffed["db"], kitting_no=MULTI, lot_no="LB", file_no="1000", start="2026/10/21 15:00:00", end="2026/10/21 18:00:00")
    sync_plans(staffed["app"])
    p = _board_plan(client)
    assert p["plan"]["planned_start"] == "2026-10-21T15:00:00+09:00"  # 最も早い計画開始
    assert any("計画開始が違います" in w for w in p["plan"]["warnings"])
    with new_session() as s:  # 同期の警告にも出る
        messages = [w.message for w in s.scalars(select(PlanSyncWarning).where(PlanSyncWarning.kitting_no == MULTI))]
    assert any("計画開始が違います" in m for m in messages)
