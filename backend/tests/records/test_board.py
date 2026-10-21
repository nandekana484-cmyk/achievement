"""ライン画面用の取得(開発指針 7.1)。"""

import pytest

from legacy_fixture import deactivate, insert_plan
from records_helpers import K1, K2, sync_plans, reason_id, start, end, ok, ev_start, ev_end


def test_board(client, staffed, fake_clock):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=150))
    ok(start(client, "production", kitting_no=K2))
    ok(end(client, "production", kitting_no=K2, produced_qty=60))
    ok(start(client, "production", kitting_no=K2, restart_reason_id=reason_id("人員交代")))  # 終了していない区切りは数えない
    ev = ok(ev_start(client, reason_id=reason_id("欠品")))

    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))

    assert b["line_code"] == "S" and b["date"] == "2026-10-21"
    assert b["current_operator"]["operator_name"] == "山田"
    assert [p["plan"]["kitting_no"] for p in b["plans"]] == [K1, K2]
    p1, p2 = b["plans"]
    assert (p1["produced_qty"], p1["progress"], p1["completed"], p1["ng_entries"]) == (150, 0.5, False, [])
    assert (p2["produced_qty"], p2["progress"]) == (60, 0.2)
    assert [e["seq"] for e in p2["events"]] == [1, 2]
    assert b["line_progress"] == pytest.approx(210 / 600)
    assert b["utilization"] is None
    assert [e["id"] for e in b["line_events"]] == [ev["id"]]
    for t in (p1["events"][0]["start_at"], p1["events"][0]["end_at"], b["current_operator"]["start_at"], b["line_events"][0]["start_at"]):
        assert t.endswith("+09:00")

    # 日付を省略すると今の稼働日(10/21 8:00 は 8:15 より前なので 10/20)
    assert ok(client.get("/api/lines/S/board"))["date"] == "2026-10-20"
    # 別の稼働日でも、片付けが終わっていない計画(遅れ)は出る。付帯作業は出ない
    other = ok(client.get("/api/lines/S/board", params={"date": "2026-10-24"}))
    assert [p["plan"]["kitting_no"] for p in other["plans"]] == [K1, K2]
    assert other["line_events"] == [] and other["line_progress"] is None


def test_board_with_zero_qty_plan(client, staffed):
    insert_plan(staffed["db"], kitting_no="0800-1-S-251014-03", file_no="0800", qty=0, start="2026/10/21 16:00:00", end="2026/10/21 17:00:00")
    sync_plans(staffed["app"])
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
    sync_plans(staffed["app"])
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert [p["progress"] for p in b["plans"]] == [None] and b["line_progress"] is None


def test_board_unknown_line(client, world):
    assert client.get("/api/lines/X/board").status_code == 404


def test_board_open_line_event_continues_until_now(client, staffed, fake_clock):
    ev = ok(ev_start(client, reason_id=reason_id("欠品")))  # 2026-10-21 08:00 に開始し、終了していない
    fake_clock.advance(days=1)  # 翌日になっても続いている
    assert [e["id"] for e in ok(client.get("/api/lines/S/board", params={"date": "2026-10-22"}))["line_events"]] == [ev["id"]]
    assert ok(client.get("/api/lines/S/board", params={"date": "2026-10-23"}))["line_events"] == []  # 今より後の日には出さない


def test_board_line_event_spanning_midnight(client, staffed, fake_clock):
    fake_clock.advance(hours=15)  # 2026-10-21 23:00
    ev = ok(ev_start(client, reason_id=reason_id("部品探し")))
    fake_clock.advance(hours=2)  # 翌日 01:00
    ok(ev_end(client, ev["id"]))
    for day in ("2026-10-21", "2026-10-22"):
        assert [e["id"] for e in ok(client.get("/api/lines/S/board", params={"date": day}))["line_events"]] == [ev["id"]]
