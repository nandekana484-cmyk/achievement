"""集計の区間の計算(稼働日の境目での分け方、上段・下段の区切り、時間)。"""

from datetime import date, datetime, time

from app.core.clock import JST
from app.domain.intervals import minutes_between, split_at, split_by_workday

DAY_START = time(8, 15)


def t(day, hm):
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=JST)


def test_split_by_workday_at_day_start():
    assert split_by_workday(t(21, "07:00"), t(21, "09:00"), DAY_START) == [
        (date(2026, 10, 20), t(21, "07:00"), t(21, "08:15")),
        (date(2026, 10, 21), t(21, "08:15"), t(21, "09:00")),
    ]


def test_split_over_several_workdays():
    pieces = split_by_workday(t(20, "20:00"), t(22, "09:00"), DAY_START)
    assert [p[0] for p in pieces] == [date(2026, 10, 20), date(2026, 10, 21), date(2026, 10, 22)]
    assert pieces[1][1:] == (t(21, "08:15"), t(22, "08:15"))


def test_within_one_workday_and_zero_length():
    assert split_by_workday(t(21, "22:00"), t(22, "02:00"), DAY_START) == [(date(2026, 10, 21), t(21, "22:00"), t(22, "02:00"))]
    assert split_by_workday(t(21, "08:15"), t(21, "08:15"), DAY_START) == [(date(2026, 10, 21), t(21, "08:15"), t(21, "08:15"))]


def test_split_at_halves():
    b = [t(21, "08:15"), t(21, "20:15"), t(22, "08:15")]
    assert split_at(t(21, "19:00"), t(21, "21:00"), b) == [(0, t(21, "19:00"), t(21, "20:15")), (1, t(21, "20:15"), t(21, "21:00"))]
    assert split_at(t(21, "07:00"), t(21, "09:00"), b) == [(0, t(21, "08:15"), t(21, "09:00"))]  # 範囲の外は捨てる
    assert split_at(t(21, "20:15"), t(21, "20:15"), b) == [(1, t(21, "20:15"), t(21, "20:15"))]


def test_minutes_have_one_decimal():
    assert minutes_between(t(21, "08:00"), t(21, "09:30")) == 90.0
    assert minutes_between(datetime(2026, 10, 21, 8, 0, 0, tzinfo=JST), datetime(2026, 10, 21, 8, 0, 20, tzinfo=JST)) == 0.3
