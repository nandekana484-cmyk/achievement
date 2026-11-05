"""遅れた未着手の計画(AD-24): 判定、表示範囲の広がり、上限と警告。"""

from datetime import datetime, time

import pytest
from sqlalchemy import update

from app.core.clock import JST
from app.db.models import RunEvent
from app.services import masters
from app.services.correction_rules import FieldScope
from legacy_fixture import insert_plan
from records_helpers import end, new_session, ok, start, sync_plans
from test_plan_closures import close

# 今(テストの時計)は 10/21 8:00。稼働日 10/21 8:15〜、通常の表示範囲 = 10/20 20:15〜10/22 20:15、広げる限度 = 10/18 8:15
DONE = "0100-1-S-251014-01"  # 10/18 9:00〜12:00。10/18 10:00 に片付けまで終えた(本アプリの使い始め = 10/18 10:00)
LAG = "0200-1-S-251014-02"  # 10/19 9:00〜12:00 未着手(遅れた未着手の計画)
LAG_OLD = "0300-1-S-251014-03"  # 10/17 21:00〜23:00 未着手(限度より古い)
LAG_BEFORE = "0400-1-S-251014-04"  # 10/17 9:00〜10:00 未着手(使い始めより前に終わった)
OVER = "0500-1-S-251014-05"  # 10/19 10:00〜11:00(LAG と時間が重なる)


def _plan(db, kno, s, e):
    insert_plan(db, kitting_no=kno, file_no=kno[:4], start=s, end=e)


@pytest.fixture
def world2(client, staffed, fake_clock):
    db = staffed["db"]
    _plan(db, DONE, "2026/10/18 09:00:00", "2026/10/18 12:00:00")
    _plan(db, LAG, "2026/10/19 09:00:00", "2026/10/19 12:00:00")
    _plan(db, LAG_OLD, "2026/10/17 21:00:00", "2026/10/17 23:00:00")
    _plan(db, LAG_BEFORE, "2026/10/17 09:00:00", "2026/10/17 10:00:00")
    sync_plans(staffed["app"])
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 18, 10, 0, tzinfo=JST)
    ok(start(client, "cleanup", kitting_no=DONE))
    ok(end(client, "cleanup", kitting_no=DONE))
    fake_clock.current = now
    with new_session() as s:
        masters.add_operator(s, "鈴木", worker_id="Z001")
    return staffed


def board(client):
    return ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))


def test_lagging_plan_widens_range(client, world2):
    b = board(client)
    assert b["display_start"] == "2026-10-18T21:00:00+09:00"  # 遅れた未着手の計画 LAG(10/19 9:00)の12時間前。LAG_OLD は使い始めより後に終わる
    assert b["display_end"] == "2026-10-22T20:15:00+09:00"
    assert LAG in [p["plan"]["kitting_no"] for p in b["plans"]]  # 範囲の中なので出る


def test_limit_and_warning(client, world2):
    with new_session() as s:  # 使い始めを 10/10 にする(LAG_OLD・LAG_BEFORE も数える)
        s.execute(update(RunEvent).where(RunEvent.kitting_no == DONE).values(start_at=datetime(2026, 10, 10, 10, 0, tzinfo=JST)))
        s.commit()
    b = board(client)
    assert b["display_start"] == "2026-10-18T08:15:00+09:00"  # 上限(稼働日の始まりの72時間前)
    stale = {p["kitting_no"]: p for p in b["stale_plans"]}
    assert set(stale) == {LAG_OLD, LAG_BEFORE}  # 範囲(10/18 8:15〜)に入らない遅れた未着手の計画
    p = stale[LAG_OLD]
    assert p["lot_nos"] and p["planned_start"] == "2026-10-17T21:00:00+09:00" and p["planned_end"] == "2026-10-17T23:00:00+09:00"
    assert LAG in [x["plan"]["kitting_no"] for x in b["plans"]] and LAG not in stale  # 範囲に入る LAG は警告に出ない


def test_before_adoption_is_ignored(client, world2):
    b = board(client)  # 使い始め(10/18 10:00)より前に終わった LAG_BEFORE は数えない
    assert b["stale_plans"] == []


def test_closed_plan_is_not_lagging(client, world2):
    ok(close(client, kno=LAG))
    assert board(client)["display_start"] == "2026-10-20T20:15:00+09:00"  # 計画終了すると範囲が元に戻る


def test_overlapping_completed_plan_excludes(client, world2, fake_clock):
    # LAG(10/19 9:00〜12:00)と時間が重なる別の計画 OVER が完了している → 計画変更で飛ばされたものとして外す
    _plan(world2["db"], OVER, "2026/10/19 10:00:00", "2026/10/19 11:00:00")
    sync_plans(world2["app"])
    now = fake_clock.current
    fake_clock.current = datetime(2026, 10, 19, 10, 0, tzinfo=JST)
    ok(start(client, "cleanup", kitting_no=OVER))
    ok(end(client, "cleanup", kitting_no=OVER))
    fake_clock.current = now
    assert board(client)["display_start"] == "2026-10-20T20:15:00+09:00"


def test_no_records_no_lagging(client, staffed):
    # 記録が1つも無い(本アプリを使い始めていない)DB では、過去の計画は遅れた未着手とみなさない
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert b["stale_plans"] == [] and b["display_start"] == "2026-10-20T20:15:00+09:00"


def test_correction_range_follows_widened_window(client, world2):
    with new_session() as s:
        lo, hi = FieldScope(s, "S", time(8, 15), 72).window(datetime(2026, 10, 21, 8, 0, tzinfo=JST))
    assert lo == datetime(2026, 10, 18, 21, 0, tzinfo=JST)  # 表示範囲と同じ(広がった範囲の記録も訂正できる)
