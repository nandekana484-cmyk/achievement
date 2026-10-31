"""訂正と完了: 完了の写しの作り直し、片付けの終了の取り消し、取り消した記録を計算から外すこと(開発指針 5.7)。"""

from app.db.models import RunCompletion
from legacy_fixture import insert_plan
from records_helpers import K1, add, at, board_plan, count_rows, end, fix, ok, reason_id, start, sync_plans, void


def _complete(client, fake_clock, qty=100):
    """生産(8:00〜9:00)と片付け(9:00〜9:10)を記録して完了にする。"""
    prod = ok(start(client, "production"))["event"]
    fake_clock.advance(minutes=60)
    ok(end(client, "production", produced_qty=qty))
    cleanup = ok(start(client, "cleanup"))["event"]
    fake_clock.advance(minutes=10)
    completion = ok(end(client, "cleanup"))["completion"]
    return prod, cleanup, completion


def test_correcting_completed_plan_rebuilds_completion(client, staffed, fake_clock):
    prod, _, first = _complete(client, fake_clock)
    fake_clock.advance(minutes=5)

    r = ok(fix(client, prod["id"], produced_qty=120, reason="wrong_qty"))

    rebuilt = r["completion"]
    assert r["completed"] is True
    assert (rebuilt["kind"], rebuilt["correction_id"], rebuilt["produced_qty"]) == ("correction", r["correction"]["id"], 120)
    assert rebuilt["completed_at"] == first["completed_at"] == at("09:10")  # 完了の時刻は片付けの終了のまま
    assert rebuilt["plan_qty_snapshot"] == first["plan_qty_snapshot"] == 300
    assert count_rows(RunCompletion) == 2
    plan = board_plan(client)
    assert plan["completed"] is True and plan["completion"]["id"] == rebuilt["id"]  # 最新を有効とする


def test_rebuilt_completion_keeps_plan_snapshot(client, staffed, fake_clock):
    prod, _, _ = _complete(client, fake_clock)
    insert_plan(staffed["db"], kitting_no=K1, qty=400, at="2026-10-21 09:00:00")  # 完了のあとで計画の数量が変わった
    sync_plans(staffed["app"])

    rebuilt = ok(fix(client, prod["id"], produced_qty=110))["completion"]

    assert rebuilt["plan_qty_snapshot"] == 300 and rebuilt["lots_snapshot"][0]["planned_qty"] == 300


def test_cleanup_end_time_correction_moves_completed_at(client, staffed, fake_clock):
    _, cleanup, _ = _complete(client, fake_clock)
    rebuilt = ok(fix(client, cleanup["id"], end_at=at("09:08")))["completion"]
    assert rebuilt["completed_at"] == at("09:08")


def test_voiding_cleanup_makes_plan_not_completed(client, staffed, fake_clock):
    prod, cleanup, _ = _complete(client, fake_clock)

    r = ok(void(client, cleanup["id"]))

    assert r["completed"] is False and r["completion"] is None
    plan = board_plan(client)
    assert plan["completed"] is False and plan["completion"] is None
    assert count_rows(RunCompletion) == 1  # 完了の行は消さない(取り消した片付けを参照するので無効)
    # 片付けをやり直せば、また完了になる
    ok(start(client, "cleanup"))
    fake_clock.advance(minutes=5)
    assert ok(end(client, "cleanup"))["completion"]["kind"] == "cleanup"
    assert board_plan(client)["completed"] is True


def test_voiding_latest_cleanup_falls_back_to_earlier_one(client, staffed, fake_clock):
    _, _, first = _complete(client, fake_clock)
    ok(start(client, "production", restart_reason_id=reason_id("計画切替")))
    fake_clock.advance(minutes=10)
    ok(end(client, "production", produced_qty=20))
    second_cleanup = ok(start(client, "cleanup"))["event"]
    fake_clock.advance(minutes=5)
    ok(end(client, "cleanup"))

    r = ok(void(client, second_cleanup["id"]))

    # 残った片付け(1回目)で作り直す。生産数は今の値(取り消していない区切りの合計)
    assert r["completed"] is True
    assert (r["completion"]["completed_at"], r["completion"]["produced_qty"]) == (first["completed_at"], 120)


def test_voiding_production_of_completed_plan(client, staffed, fake_clock):
    prod, _, _ = _complete(client, fake_clock)
    r = ok(void(client, prod["id"]))
    assert r["completion"]["produced_qty"] == 0
    assert board_plan(client)["progress"] is None  # 完了した計画に進捗率は出さない


def test_adding_forgotten_cleanup_completes_plan(client, staffed, fake_clock):
    ok(start(client, "production"))
    fake_clock.advance(minutes=60)
    ok(end(client, "production", produced_qty=300))
    fake_clock.advance(minutes=30)  # 9:30。片付けの押し忘れ

    r = ok(add(client, "cleanup", at("09:00"), at("09:20")))

    assert r["completed"] is True and r["completion"]["kind"] == "correction"
    assert r["completion"]["completed_at"] == at("09:20") and r["completion"]["produced_qty"] == 300
    assert board_plan(client)["completed"] is True


def test_correcting_incomplete_plan_does_not_complete(client, staffed, fake_clock):
    prod = ok(start(client, "production"))["event"]
    fake_clock.advance(minutes=30)
    ok(end(client, "production", produced_qty=10))
    r = ok(fix(client, prod["id"], produced_qty=12))
    assert r["completed"] is False and r["completion"] is None
    assert count_rows(RunCompletion) == 0


def test_voided_records_leave_efficiency_and_board(client, staffed, fake_clock):
    prod = ok(start(client, "production"))["event"]
    fake_clock.advance(minutes=30)
    ok(end(client, "production", produced_qty=150))
    board = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert board["efficiency"]["included"] == 1
    ok(void(client, prod["id"]))
    board = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert board["efficiency"]["included"] == 0 and board["efficiency"]["efficiency"] is None  # 取り消した記録は入れない


def test_plan_with_only_voided_records_counts_as_untouched(client, staffed, fake_clock):
    # 計画終了が過ぎた計画。押し間違いで始めた記録を取り消したら、未着手で過ぎた計画として画面に出さない
    past = "0200-1-S-251014-02"
    insert_plan(staffed["db"], kitting_no=past, file_no="0200", start="2026/10/20 21:00:00", end="2026/10/20 23:00:00")
    sync_plans(staffed["app"])
    e = ok(start(client, "setup", kitting_no=past))["event"]
    shown = lambda: past in [p["plan"]["kitting_no"] for p in ok(client.get("/api/lines/S/board"))["plans"]]  # noqa: E731
    assert shown()
    ok(void(client, e["id"], kitting_no=past))
    assert not shown()
