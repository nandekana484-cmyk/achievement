"""完了(開発指針 5.7)。"""

from app.db.models import RunCompletion
from legacy_fixture import insert_plan
from records_helpers import K1, rid, sync_plans, count_rows, reason_id, start, end, ok


def _ng(client, lot_no, qty):
    ok(client.put(f"/api/runs/{K1}/ng-qty", json={"request_id": rid(), "lot_no": lot_no, "side": 1, "ng_qty": qty}))


def test_cleanup_end_completes_with_snapshots(client, staffed):
    # K1 にロット L002(200枚、基板B)を足す → まとまりの計画数は 300 + 200 = 500
    insert_plan(staffed["db"], kitting_no=K1, lot_no="L002", qty=200, board="基板B")
    sync_plans(staffed["app"])
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    ok(start(client, "production", restart_reason_id=reason_id("人員交代")))
    ok(end(client, "production", produced_qty=150))
    _ng(client, "L001", 3)
    _ng(client, "L001", 5)
    _ng(client, "L002", 1)
    ok(start(client, "cleanup"))

    r = ok(end(client, "cleanup"))

    c = r["completion"]
    assert (c["produced_qty"], c["plan_qty_snapshot"], c["takt_sec_snapshot"]) == (250, 500, 30.0)
    assert c["lots_snapshot"] == [
        {"lot_no": "L001", "product_name": "基板A", "planned_qty": 300},
        {"lot_no": "L002", "product_name": "基板B", "planned_qty": 200},
    ]
    assert [(n["lot_no"], n["side"], n["side_kitting_no"], n["ng_qty"]) for n in c["ng_snapshot"]] == [
        ("L001", 1, K1, 5), ("L002", 1, K1, 1),  # ロットと面ごとの最新のNG数
    ]
    assert c["utilization"] is None and c["completed_at"] == r["event"]["end_at"]

    # あとで計画の数量が変わっても、完了の写しは変わらない
    insert_plan(staffed["db"], kitting_no=K1, qty=400, at="2026-10-21 09:00:00")
    sync_plans(staffed["app"])
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["plan"]["planned_qty"] == 600
    assert plan["completed"] is True and plan["completion"]["plan_qty_snapshot"] == 500
    assert plan["completion"]["lots_snapshot"][0]["planned_qty"] == 300


def test_other_steps_do_not_complete(client, staffed):
    ok(start(client, "setup"))
    assert ok(end(client, "setup"))["completion"] is None
    assert count_rows(RunCompletion) == 0


def test_cleanup_again_adds_completion_and_latest_wins(client, staffed, fake_clock):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    ok(start(client, "cleanup"))
    ok(end(client, "cleanup"))

    # 完了後も工程の記録は受け付ける
    ok(start(client, "production", restart_reason_id=reason_id("計画切替")))
    ok(end(client, "production", produced_qty=20))
    fake_clock.advance(minutes=10)
    ok(start(client, "cleanup"))
    second = ok(end(client, "cleanup"))["completion"]

    assert second["produced_qty"] == 120
    assert count_rows(RunCompletion) == 2
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["completion"]["id"] == second["id"]


def test_completion_resend_does_not_duplicate(client, staffed):
    ok(start(client, "cleanup"))
    request_id = rid()
    first = ok(end(client, "cleanup", request_id=request_id))
    assert ok(end(client, "cleanup", request_id=request_id)) == first
    assert count_rows(RunCompletion) == 1
