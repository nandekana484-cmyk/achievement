"""集計の「時間の区間」の計算(DBに触らない)。詳細: docs/design/reports.md"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.domain.workday import workday_of, workday_range


def split_by_workday(start: datetime, end: datetime, day_start: time) -> list[tuple[date, datetime, datetime]]:
    """開始〜終了を稼働日の境目で分け、(稼働日, 開始, 終了) の並びにする。長さ0でも1つ返す。"""
    if end <= start:
        return [(workday_of(start, day_start), start, start)]
    pieces = []
    s = start
    while s < end:
        day = workday_of(s, day_start)
        e = min(end, workday_range(day, day_start)[1])
        pieces.append((day, s, e))
        s = e
    return pieces


def split_at(start: datetime, end: datetime, boundaries: list[datetime]) -> list[tuple[int, datetime, datetime]]:
    """開始〜終了を boundaries(昇順)の区切りで分け、(区切りの番号, 開始, 終了) にする。範囲の外は捨てる(日報の上段・下段)。"""
    out = []
    for i in range(len(boundaries) - 1):
        s, e = max(start, boundaries[i]), min(end, boundaries[i + 1])
        if s < e or (s == e == start and boundaries[i] <= start < boundaries[i + 1]):
            out.append((i, s, e))
    return out


def minutes_between(start: datetime, end: datetime) -> float:
    """時間(分。小数1桁)。"""
    return round((end - start) / timedelta(minutes=1), 1)
