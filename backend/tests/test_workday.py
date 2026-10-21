"""稼働日(day_start 〜 翌日の day_start)と表示範囲。"""

from datetime import date, datetime, time

import pytest

from app.core.clock import JST
from app.core.config import load_config
from app.domain.workday import display_range, workday_of, workday_range

DAY_START = time(8, 15)


def at(y, mo, d, h, mi, s=0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=JST)


@pytest.mark.parametrize(
    ("t", "expected"),
    [
        (at(2026, 10, 21, 8, 14, 59), date(2026, 10, 20)),  # 8:15 より前は前日の稼働日
        (at(2026, 10, 21, 8, 15), date(2026, 10, 21)),  # 8:15 から当日の稼働日
        (at(2026, 10, 21, 23, 59), date(2026, 10, 21)),
        (at(2026, 10, 22, 0, 0), date(2026, 10, 21)),  # 日付をまたいでも、8:15 までは前日の稼働日
        (at(2026, 10, 22, 8, 14), date(2026, 10, 21)),
        (at(2026, 11, 1, 3, 0), date(2026, 10, 31)),  # 月をまたぐ
        (at(2027, 1, 1, 8, 0), date(2026, 12, 31)),  # 年をまたぐ
    ],
)
def test_workday_of(t, expected):
    assert workday_of(t, DAY_START) == expected


def test_workday_of_converts_to_jst():
    utc = datetime.fromisoformat("2026-10-20T23:15:00+00:00")  # 日本時間 10/21 8:15
    assert workday_of(utc, DAY_START) == date(2026, 10, 21)


def test_other_day_start():
    assert workday_of(at(2026, 10, 21, 5, 59), time(6, 0)) == date(2026, 10, 20)
    assert workday_of(at(2026, 10, 21, 6, 0), time(6, 0)) == date(2026, 10, 21)
    assert workday_of(at(2026, 10, 21, 0, 0), time(0, 0)) == date(2026, 10, 21)  # 0:00 なら暦の日と同じ
    assert workday_range(date(2026, 10, 21), time(6, 0)) == (at(2026, 10, 21, 6, 0), at(2026, 10, 22, 6, 0))


def test_workday_and_display_range():
    assert workday_range(date(2026, 10, 21), DAY_START) == (at(2026, 10, 21, 8, 15), at(2026, 10, 22, 8, 15))
    # 表示範囲 = 稼働日の始まりの12時間前から、終わりの12時間後まで(48時間)
    assert display_range(date(2026, 10, 21), DAY_START) == (at(2026, 10, 20, 20, 15), at(2026, 10, 22, 20, 15))


def test_day_start_from_config(tmp_path):
    assert load_config(tmp_path / "none.toml").schedule.day_start == time(8, 15)
    p = tmp_path / "config.toml"
    p.write_text('[schedule]\nday_start = "06:30"\n', encoding="utf-8")
    assert load_config(p).schedule.day_start == time(6, 30)


def test_example_config_has_day_start():
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "config.example.toml"
    assert load_config(example).schedule.day_start == time(8, 15)
