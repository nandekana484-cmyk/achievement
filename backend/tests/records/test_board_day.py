"""ライン画面で、今日以外の稼働日を見るとき(AD-25): 前後12時間だけを出し、範囲を広げず、範囲の外の操作は断る。"""

from datetime import datetime

import pytest

from app.core.clock import JST
from legacy_fixture import insert_plan
from records_helpers import add, at, conflict, ok, start, sync_plans

# 今(テストの時計)は 10/21 8:00。まだ 8:15 前なので、今日の稼働日は 10/20(通常の表示範囲 = 10/19 20:15〜10/21 20:15)
STARTED = "0300-1-S-251014-04"  # 10/19 に始め、片付けが終わっていない
LAG = "0200-1-S-251014-02"  # 10/19 9:00〜12:00 未着手(遅れた未着手の計画)
ON_21 = "0400-1-S-251014-06"  # 10/21 9:00〜12:00
ON_24 = "0500-1-S-251014-07"  # 10/24 9:00〜12:00


def _board(client, day=None):
    return ok(client.get("/api/lines/S/board", params={"date": day} if day else {}))


def _shown(b):
    return [p["plan"]["kitting_no"] for p in b["plans"]]


@pytest.fixture
def world3(client, staffed, fake_clock):
    db = staffed["db"]
    for kno, s, e in [(STARTED, "10/19 09:00", "10/19 12:00"), (LAG, "10/19 09:30", "10/19 12:00"),
                      (ON_21, "10/21 09:00", "10/21 12:00"), (ON_24, "10/24 09:00", "10/24 12:00")]:
        insert_plan(db, kitting_no=kno, file_no=kno[:4], start=f"2026/{s}:00", end=f"2026/{e}:00")
    sync_plans(staffed["app"])
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 19, 10, 0, tzinfo=JST)
    ok(start(client, "setup", kitting_no=STARTED))
    fake_clock.current = now
    return staffed


def test_today_is_default_and_widens(client, world3):
    b = _board(client)
    assert b["date"] == "2026-10-20" and b["display_start"] == "2026-10-18T22:00:00+09:00"  # 片付けが終わっていない計画で広がる
    assert STARTED in _shown(b)


def test_other_day_is_48_hours_only(client, world3):
    b = _board(client, "2026-10-24")
    assert b["date"] == "2026-10-24"
    assert b["display_start"] == "2026-10-23T20:15:00+09:00" and b["display_end"] == "2026-10-25T20:15:00+09:00"  # 稼働日の前後12時間
    assert _shown(b) == [ON_24]  # 片付けが終わっていない計画も、遅れた未着手の計画も出さない
    assert b["stale_kitting_nos"] == [] and b["stale_plans"] == [] and b["stale_plans_total"] == 0


def test_past_day_does_not_widen(client, world3):
    b = _board(client, "2026-10-17")
    assert b["display_start"] == "2026-10-16T20:15:00+09:00" and b["display_end"] == "2026-10-18T20:15:00+09:00"
    assert _shown(b) == [] and b["stale_plans"] == []
    assert STARTED in _shown(_board(client, "2026-10-19"))  # 範囲に重なる計画は出る


def test_operations_outside_today_range_are_refused(client, world3):
    # ほかの日を見ていても、サーバーは今日の表示範囲の外の操作を断る
    conflict(add(client, "setup", at("19:00", day=16), at("19:30", day=16), kitting_no=ON_24), "範囲の外の時刻は管理画面から直してください")
