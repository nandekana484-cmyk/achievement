"""ライン画面の表示範囲の広げ方(片付けが終わっていない計画)と、計画終了を過ぎた未着手の計画(詳細: docs/design/line-screen.md)。"""

from datetime import datetime

import pytest

from app.core.clock import JST
from legacy_fixture import insert_plan
from records_helpers import end, ok, start, sync_plans

# 今(テストの時計)は 10/21 8:00。稼働日 10/21 8:15〜、通常の表示範囲 = 10/20 20:15〜10/22 20:15
UNTOUCHED_IN = "0200-1-S-251014-02"  # 10/20 21:00〜23:00(範囲の中。計画終了が過ぎて未着手)
UNTOUCHED_OUT = "0210-1-S-251014-03"  # 10/20 09:00〜12:00(範囲の外。未着手)
STARTED = "0300-1-S-251014-04"  # 10/19 に始め、片付けが終わっていない
STARTED_OLD = "0310-1-S-251014-05"  # 10/15 に始め、片付けが終わっていない(広げる限度より前)


def _knos(client) -> dict:
    return ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))


def _shown(board: dict) -> list[str]:
    return [p["plan"]["kitting_no"] for p in board["plans"]]


@pytest.fixture
def world(client, staffed, fake_clock):
    db = staffed["db"]
    insert_plan(db, kitting_no=UNTOUCHED_IN, file_no="0200", start="2026/10/20 21:00:00", end="2026/10/20 23:00:00")
    insert_plan(db, kitting_no=UNTOUCHED_OUT, file_no="0210", start="2026/10/20 09:00:00", end="2026/10/20 12:00:00")
    insert_plan(db, kitting_no=STARTED, file_no="0300", start="2026/10/19 09:00:00", end="2026/10/19 12:00:00")
    insert_plan(db, kitting_no=STARTED_OLD, file_no="0310", start="2026/10/15 09:00:00", end="2026/10/15 12:00:00")
    sync_plans(staffed["app"])
    return staffed


def test_overdue_untouched_plan_in_range_is_shown(client, world):
    shown = _shown(_knos(client))
    assert UNTOUCHED_IN in shown  # 計画終了を過ぎて未着手でも、表示範囲と重なれば出る
    assert UNTOUCHED_OUT not in shown  # 範囲の外は出ない(検索で選ぶ)


def test_cancelled_plan_is_not_shown(client, world):
    from sqlalchemy import update

    from app.db.models import Plan
    from records_helpers import new_session

    with new_session() as s:
        s.execute(update(Plan).where(Plan.kitting_no == UNTOUCHED_IN).values(status="cancelled"))
        s.commit()
    assert UNTOUCHED_IN not in _shown(_knos(client))


def test_range_widens_to_12h_before_first_record(client, world, fake_clock):
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 19, 10, 0, tzinfo=JST)
    ok(start(client, "setup", kitting_no=STARTED))
    fake_clock.current = now
    b = _knos(client)
    assert b["display_start"] == "2026-10-18T22:00:00+09:00"  # 最初の記録(10/19 10:00)の12時間前
    assert b["display_end"] == "2026-10-22T20:15:00+09:00"  # 終わりは今のまま
    assert b["stale_kitting_nos"] == []
    assert UNTOUCHED_OUT in _shown(b)  # 広げた範囲の中の計画(10/20 9:00〜12:00)は、範囲と重なれば未着手でも出る
    assert STARTED in _shown(b)


def test_range_uses_oldest_unfinished_plan_and_stops_at_limit(client, world, fake_clock):
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 19, 10, 0, tzinfo=JST)
    ok(start(client, "setup", kitting_no=STARTED))
    fake_clock.current = datetime(2026, 10, 15, 10, 0, tzinfo=JST)
    ok(start(client, "setup", kitting_no=STARTED_OLD))
    fake_clock.current = now
    b = _knos(client)
    assert b["display_start"] == "2026-10-18T08:15:00+09:00"  # 稼働日の始まりの72時間前が限度
    assert b["stale_kitting_nos"] == [STARTED_OLD]  # 限度より古い計画は警告する
    assert STARTED_OLD in _shown(b) and STARTED in _shown(b)  # 選べるよう、board には出す


def test_finished_plan_does_not_widen_range(client, world, fake_clock):
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 19, 10, 0, tzinfo=JST)
    ok(start(client, "cleanup", kitting_no=STARTED))
    ok(end(client, "cleanup", kitting_no=STARTED))
    fake_clock.current = now
    # 完了した計画は広げない。広がるのは、遅れた未着手の計画(UNTOUCHED_OUT。10/20 9:00)の12時間前まで(完了した計画の記録 10/19 10:00 の12時間前より新しい)
    assert _knos(client)["display_start"] == "2026-10-19T21:00:00+09:00"


def test_all_plans_in_range_are_shown(client, world, fake_clock):
    # 表示範囲の中の、完了した計画・片付けが終わっていない計画・始まっていない計画(計画終了を過ぎたものを含む)は、すべて board に出る
    done, doing = "0400-1-S-251014-04", "0410-1-S-251014-05"
    insert_plan(world["db"], kitting_no=done, file_no="0400", start="2026/10/20 21:00:00", end="2026/10/20 22:00:00")
    insert_plan(world["db"], kitting_no=doing, file_no="0410", start="2026/10/20 22:00:00", end="2026/10/20 23:00:00")
    sync_plans(world["app"])
    ok(start(client, "cleanup", kitting_no=done))
    ok(end(client, "cleanup", kitting_no=done))
    ok(start(client, "setup", kitting_no=doing))
    shown = _shown(_knos(client))
    assert done in shown and doing in shown  # 完了、片付け前
    assert UNTOUCHED_IN in shown  # 計画終了を過ぎて未着手
    assert "0900-1-S-251014-09" not in shown
