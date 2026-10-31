"""効率と進捗率の計算。ライン画面のバー・日報・区間の CSV が同じ値になるよう、計算はここだけで行う。DBは読むだけ。

- 効率 = Σ(目標タクト × 良品台数 ÷ 丁取り数) ÷ Σ(実所要時間)。付帯作業と重なる分は実所要時間から引く
- 進捗率 = 生産中の計画の、工程の記録の時間の合計 ÷ 計画の時間
詳細: docs/design/metrics.md
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import LineEvent, RunEvent
from app.services.completions import latest_completion
from app.services.efficiency_inputs import inputs_for
from app.services.kitting_plans import KittingGroup, load_group
from app.services.views.metrics import EfficiencyOut, ExcludedPlanOut, ProgressOut, ReasonCountOut
from app.services.report_intervals import KIND_LINE_EVENT, KIND_STEP, IntervalOut

Span = tuple[dt.datetime, dt.datetime]


def _merge(spans: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _net_seconds(start: dt.datetime, end: dt.datetime, merged_events: list[Span]) -> float:
    """工程の時間(秒)から、付帯作業と重なる分を引く。付帯作業どうしの重なりは1回だけ引く。"""
    total = (end - start).total_seconds()
    overlap = sum(max(0.0, (min(end, e) - max(start, s)).total_seconds()) for s, e in merged_events)
    return max(0.0, total - overlap)


def _end_of(start: dt.datetime, end: dt.datetime | None, now: dt.datetime) -> dt.datetime:
    return end if end is not None else max(now, start)  # 作業中の記録は今の時刻まで数える


def efficiency_from_intervals(session: Session, line_code: str, intervals: list[IntervalOut], now: dt.datetime) -> EfficiencyOut:
    """1つの稼働日・1つのラインの区間(report_intervals.build_intervals の結果)から効率を出す。"""
    events = _merge([(i.start, _end_of(i.start, i.end, now)) for i in intervals
                     if i.kind == KIND_LINE_EVENT and i.line_code == line_code])
    actual: dict[str, float] = {}
    good: Counter[str] = Counter()
    for i in intervals:
        if i.kind != KIND_STEP or i.line_code != line_code or i.kitting_no is None:
            continue
        actual[i.kitting_no] = actual.get(i.kitting_no, 0.0) + _net_seconds(i.start, _end_of(i.start, i.end, now), events)
        good[i.kitting_no] += i.produced_qty or 0

    standard = used = 0.0
    included = 0
    excluded: list[ExcludedPlanOut] = []
    warnings: list[str] = []
    for kno in sorted(actual):
        inputs = inputs_for(session, load_group(session, kno))
        warnings += inputs.warnings
        reason = inputs.excluded_reason
        if reason is not None:  # 分子と分母の両方から外す
            excluded.append(ExcludedPlanOut(kitting_no=kno, reason=reason))
            continue
        included += 1
        used += actual[kno]
        standard += inputs.takt_sec * good[kno] / inputs.teitori  # 枚数は切り上げない
    counts = Counter(x.reason for x in excluded)
    return EfficiencyOut(
        efficiency=standard / used if used > 0 else None, standard_seconds=standard, actual_seconds=used,
        included=included, excluded=len(excluded), reasons=[ReasonCountOut(reason=r, count=n) for r, n in sorted(counts.items())],
        excluded_plans=excluded, warnings=warnings,
    )


def plan_progress(session: Session, group: KittingGroup, now: dt.datetime) -> ProgressOut:
    """計画のまとまりの進捗率 = 工程の記録の時間の合計 ÷ (計画終了 − 計画開始)。"""
    events = list(session.scalars(select(RunEvent).where(RunEvent.kitting_no == group.kitting_no, RunEvent.voided_at.is_(None))))
    if not events or latest_completion(session, group.kitting_no) is not None:
        return ProgressOut(in_progress=False, progress=None)
    start, end = group.planned_start, group.planned_end
    if start is None or end is None or end <= start:
        return ProgressOut(in_progress=True, progress=None)

    first = min(e.start_at for e in events)
    last = max(_end_of(e.start_at, e.end_at, now) for e in events)
    line_events = session.scalars(select(LineEvent).where(
        LineEvent.line_code == group.line_code, LineEvent.voided_at.is_(None), LineEvent.start_at < last,
        or_(LineEvent.end_at.is_(None), LineEvent.end_at > first)))
    merged = _merge([(le.start_at, _end_of(le.start_at, le.end_at, now)) for le in line_events])
    seconds = sum(_net_seconds(e.start_at, _end_of(e.start_at, e.end_at, now), merged) for e in events)
    return ProgressOut(in_progress=True, progress=seconds / (end - start).total_seconds())
