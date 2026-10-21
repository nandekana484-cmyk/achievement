"""ライン画面に出す計画の条件(表示範囲・先行・遅れ・未着手で過ぎた計画)と、稼働日のラインの進捗率。"""

from datetime import datetime, time

import pytest

from app.core.clock import JST
from app.services.board import get_board
from legacy_fixture import insert_plan
from records_helpers import K1, K2, new_session, ok, reason_id, start, end, sync_plans

# 稼働日 10/21 = 10/21 8:15〜10/22 8:15、表示範囲 = 10/20 20:15〜10/22 20:15。今(テストの時計)は 10/21 8:00
IN_RANGE = "0100-1-S-251014-01"  # 10/21 9:00〜12:00(これから)
PAST_UNTOUCHED = "0200-1-S-251014-02"  # 10/20 21:00〜23:00(過ぎて未着手)
PAST_STARTED = "0300-1-S-251014-03"  # 10/20 21:00〜23:00(過ぎたが始めた)
AHEAD = "0400-1-S-251014-04"  # 10/23 9:00〜12:00(先行して始め、片付けまで終えた)
LATE = "0500-1-S-251014-05"  # 10/15 9:00〜12:00(10/16 に始め、片付けが終わっていない)
LATE_DONE = "0600-1-S-251014-06"  # 10/15 9:00〜12:00(10/16 に始め、片付けまで終えた)
FUTURE = "0700-1-S-251014-07"  # 10/25 9:00〜12:00(表示範囲の外で未着手)


def _plan(db, kno, start_at, end_at, qty=300):
    insert_plan(db, kitting_no=kno, file_no=kno[:4], start=start_at, end=end_at, qty=qty)


@pytest.fixture
def plans(client, staffed, fake_clock):
    db = staffed["db"]
    _plan(db, IN_RANGE, "2026/10/21 09:00:00", "2026/10/21 12:00:00")
    _plan(db, PAST_UNTOUCHED, "2026/10/20 21:00:00", "2026/10/20 23:00:00")
    _plan(db, PAST_STARTED, "2026/10/20 21:00:00", "2026/10/20 23:00:00")
    _plan(db, AHEAD, "2026/10/23 09:00:00", "2026/10/23 12:00:00", qty=100)
    _plan(db, LATE, "2026/10/15 09:00:00", "2026/10/15 12:00:00")
    _plan(db, LATE_DONE, "2026/10/15 09:00:00", "2026/10/15 12:00:00")
    _plan(db, FUTURE, "2026/10/25 09:00:00", "2026/10/25 12:00:00")
    sync_plans(staffed["app"])

    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 16, 10, 0, tzinfo=JST)  # 過去に始めた記録を作る
    ok(start(client, "setup", kitting_no=LATE))
    ok(start(client, "cleanup", kitting_no=LATE_DONE))
    ok(end(client, "cleanup", kitting_no=LATE_DONE))
    fake_clock.current = now

    ok(start(client, "setup", kitting_no=PAST_STARTED))
    for step in ("production", "cleanup"):
        ok(start(client, step, kitting_no=AHEAD))
    ok(end(client, "production", kitting_no=AHEAD, produced_qty=100))
    ok(end(client, "cleanup", kitting_no=AHEAD))
    ok(start(client, "production", kitting_no=IN_RANGE))
    ok(end(client, "production", kitting_no=IN_RANGE, produced_qty=150))
    return staffed


def _knos(board: dict) -> list[str]:
    return [p["plan"]["kitting_no"] for p in board["plans"]]


def test_plans_shown_on_board(client, plans):
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    shown = _knos(b)

    assert IN_RANGE in shown  # 1. 計画が表示範囲と重なる
    assert PAST_STARTED in shown  # 1. 過ぎていても始めていれば出る
    assert AHEAD in shown  # 2. 表示範囲の中に実績がある(先行。片付けまで終えていても出る)
    assert LATE in shown  # 3. 始めたが片付けが終わっていない(遅れ。日付は問わない)
    assert PAST_UNTOUCHED not in shown  # 計画終了が過ぎたのに未着手 → 出さない(検索で選ぶ)
    assert LATE_DONE not in shown  # 表示範囲の外で、片付けまで終えた
    assert FUTURE not in shown  # 表示範囲の外で、未着手
    assert shown == [LATE, PAST_STARTED, IN_RANGE, K1, K2, AHEAD]  # 計画開始の順(world の K1・K2 も 10/21)


def test_board_ranges_and_server_time(client, plans, fake_clock):
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert (b["workday_start"], b["workday_end"]) == ("2026-10-21T08:15:00+09:00", "2026-10-22T08:15:00+09:00")
    assert (b["display_start"], b["display_end"]) == ("2026-10-20T20:15:00+09:00", "2026-10-22T20:15:00+09:00")
    assert b["server_time"] == fake_clock.current.isoformat()


def test_line_progress_uses_only_plans_in_workday(client, plans):
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    # 稼働日(10/21 8:15〜)に重なるのは IN_RANGE・K1・K2(各300)。先行の AHEAD(10/23 の計画、100生産)は数えない
    assert b["line_progress"] == pytest.approx(150 / 900)


def test_untouched_past_plan_counts_in_line_progress(client, plans, fake_clock):
    fake_clock.current = datetime(2026, 10, 21, 13, 0, tzinfo=JST)  # IN_RANGE の計画終了を過ぎた
    insert_plan(plans["db"], kitting_no="0800-1-S-251014-08", file_no="0800", start="2026/10/21 09:00:00",
                end="2026/10/21 10:00:00", qty=300)
    sync_plans(plans["app"])
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert "0800-1-S-251014-08" not in _knos(b)  # 画面には出さないが
    assert b["line_progress"] == pytest.approx(150 / 1200)  # 進捗率の計画数には入れる


def test_other_day_start(client, plans, fake_clock):
    with new_session() as s:
        b = get_board(s, "S", None, time(6, 0))  # 今(10/21 8:00)は 6:00 区切りなら 10/21 の稼働日
    assert b.date.isoformat() == "2026-10-21"
    assert b.workday_start.isoformat() == "2026-10-21T06:00:00+09:00"


def test_get_run_for_plan_outside_display_range(client, plans):
    r = ok(client.get(f"/api/runs/{PAST_UNTOUCHED}/L001"))
    assert r["plan"]["kitting_no"] == PAST_UNTOUCHED and r["events"] == [] and r["completed"] is False
    assert client.get("/api/runs/9999-1-S-251014-99/L001").status_code == 404


def test_restart_reason_still_required_for_late_plan(client, plans):
    # 遅れの計画も、選べば同じルールで記録できる
    ok(start(client, "production", kitting_no=LATE))
    ok(end(client, "production", kitting_no=LATE, produced_qty=5))
    ok(start(client, "production", kitting_no=LATE, restart_reason_id=reason_id("人員交代")))
