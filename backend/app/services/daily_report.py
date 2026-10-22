"""日報(管理画面で表示・印刷する)。ラインと稼働日の区間を、上段(day_start から12時間)と下段(残りの12時間)の棒にする。

行は キッティングNo.ごとに1行(最初の開始の順)と、付帯作業の1行。DBは読むだけ。詳細: docs/design/reports.md
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import clock
from app.domain.intervals import split_at
from app.domain.workday import workday_range
from app.services.masters import get_line
from app.services.ng_inputs import latest_ng
from app.services.report_intervals import KIND_LINE_EVENT, IntervalOut, build_intervals
from app.services.views import LineOut, line_out

HALF = dt.timedelta(hours=12)


class HalfOut(BaseModel):
    start: dt.datetime
    end: dt.datetime


class BarOut(BaseModel):
    half: int  # 0 = 上段、1 = 下段
    start: dt.datetime
    end: dt.datetime
    step_type: str | None  # 工程のとき(画面で略称と色にする)
    label: str  # 付帯作業の理由(設備・記入を添える)。工程は工程の名前
    open: bool  # 作業中


class RowOut(BaseModel):
    kind: str  # step(キッティングNo.の行)/ line_event(付帯作業の行)
    kitting_no: str | None
    product_names: str
    bars: list[BarOut]


class DailyReportOut(BaseModel):
    line: LineOut
    date: dt.date  # 稼働日
    workday_start: dt.datetime
    workday_end: dt.datetime
    halves: list[HalfOut]
    generated_at: dt.datetime  # 出力した日時
    produced_total: int  # 生産数の合計(この稼働日の生産の区切り)
    ng_total: int  # NG数の合計(日報に出る計画の最新のNG数)
    rows: list[RowOut]
    intervals: list[IntervalOut]


def _label(i: IntervalOut) -> str:
    extra = [x for x in (i.equipment, i.reason_text) if x]
    return f"{i.what}({'・'.join(extra)})" if extra else i.what


def _bars(intervals: list[IntervalOut], boundaries: list[dt.datetime], now: dt.datetime) -> list[BarOut]:
    bars = []
    for i in intervals:
        for half, s, e in split_at(i.start, i.end or now, boundaries):
            bars.append(BarOut(half=half, start=s, end=e, step_type=i.step_type, label=_label(i), open=i.open))
    return bars


def _rows(intervals: list[IntervalOut], boundaries: list[dt.datetime], now: dt.datetime) -> list[RowOut]:
    by_kno: dict[str, list[IntervalOut]] = {}
    for i in intervals:
        if i.kind != KIND_LINE_EVENT:
            by_kno.setdefault(i.kitting_no or "", []).append(i)
    rows = [RowOut(kind="step", kitting_no=k, product_names=items[0].product_names, bars=_bars(items, boundaries, now))
            for k, items in sorted(by_kno.items(), key=lambda kv: min(x.start for x in kv[1]))]
    events = [i for i in intervals if i.kind == KIND_LINE_EVENT]
    if events:
        rows.append(RowOut(kind=KIND_LINE_EVENT, kitting_no=None, product_names="", bars=_bars(events, boundaries, now)))
    return rows


def daily_report(session: Session, line_code: str, day: dt.date, day_start: dt.time) -> DailyReportOut:
    line = get_line(session, line_code)
    start, end = workday_range(day, day_start)
    boundaries = [start, start + HALF, end]
    now = clock.now()
    intervals = build_intervals(session, day, day, line.line_code, day_start)
    rows = _rows(intervals, boundaries, now)
    knos = [r.kitting_no for r in rows if r.kitting_no]
    # TODO(要確認): 日報のNG数の合計の数え方(今は 日報に出る計画の、ロットと面ごとの最新のNG数の合計。日をまたぐ計画は各日に出る)
    ng_total = sum(n.ng_qty for k in knos for n in latest_ng(session, k))
    return DailyReportOut(
        line=line_out(line), date=day, workday_start=start, workday_end=end,
        halves=[HalfOut(start=boundaries[i], end=boundaries[i + 1]) for i in range(2)], generated_at=now,
        produced_total=sum(i.produced_qty or 0 for i in intervals), ng_total=ng_total, rows=rows, intervals=intervals,
    )
