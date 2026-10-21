"""稼働日(day_start〜翌日の day_start。開発指針 2)と表示範囲。詳細: docs/design/line-screen.md"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.core.clock import JST

DISPLAY_MARGIN = timedelta(hours=12)  # 表示範囲 = 稼働日の前後12時間を足した48時間


def workday_of(t: datetime, day_start: time) -> date:
    """その時刻が属する稼働日。"""
    local = t.astimezone(JST)
    return local.date() if local.time() >= day_start else local.date() - timedelta(days=1)


def workday_range(day: date, day_start: time) -> tuple[datetime, datetime]:
    """稼働日の始まりと終わり(終わりは含まない)。"""
    start = datetime.combine(day, day_start, tzinfo=JST)
    return start, start + timedelta(days=1)


def display_range(day: date, day_start: time) -> tuple[datetime, datetime]:
    """ライン画面の表示範囲(稼働日の始まりの12時間前から、終わりの12時間後まで)。"""
    start, end = workday_range(day, day_start)
    return start - DISPLAY_MARGIN, end + DISPLAY_MARGIN
