"""ライン画面用の取得(開発指針 7.1)。DBは読むだけ。"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_ACTIVE, LineEvent, Plan, RunEvent
from app.services.line_operators import current_row
from app.services.masters import get_line
from app.services.run_records import latest_completion, latest_ng_qty, produced_total
from app.services.views import (
    BoardOut,
    BoardPlanOut,
    current_operator_out,
    line_event_out,
    plan_out,
    run_completion_out,
    run_event_out,
)


def _day_range(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(day, dt.time(), tzinfo=clock.JST)
    return start, start + dt.timedelta(days=1)


def plans_for_day(session: Session, line_code: str, day: dt.date) -> list[Plan]:
    """その日に計画開始〜終了が重なる有効な計画を、計画開始の順で返す。"""
    day_start, day_end = _day_range(day)
    stmt = (
        select(Plan)
        .where(
            Plan.line_code == line_code,
            Plan.status == PLAN_ACTIVE,
            Plan.planned_start.is_not(None),
            Plan.planned_end.is_not(None),
            Plan.planned_start < day_end,
            Plan.planned_end > day_start,
        )
        .order_by(Plan.planned_start, Plan.kitting_no, Plan.lot_no)
    )
    return list(session.scalars(stmt))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def get_board(session: Session, line_code: str, day: dt.date | None = None) -> BoardOut:
    line = get_line(session, line_code)
    day = day or clock.now().date()
    day_start, day_end = _day_range(day)

    plans: list[BoardPlanOut] = []
    for p in plans_for_day(session, line.line_code, day):
        events = session.scalars(
            select(RunEvent).where(RunEvent.kitting_no == p.kitting_no, RunEvent.lot_no == p.lot_no)
            .order_by(RunEvent.start_at, RunEvent.id)
        )
        produced = produced_total(session, p.kitting_no, p.lot_no)
        completion = latest_completion(session, p.kitting_no, p.lot_no)
        plans.append(BoardPlanOut(
            plan=plan_out(p),
            events=[run_event_out(session, e) for e in events],
            produced_qty=produced,
            ng_qty=latest_ng_qty(session, p.kitting_no, p.lot_no),
            completed=completion is not None,
            completion=run_completion_out(completion) if completion is not None else None,
            progress=_ratio(produced, p.planned_qty),
        ))

    # その日に重なる付帯作業。終了していないものは今まで続いているとみなす(今より後の日には出さない)
    still_open = LineEvent.end_at.is_(None) if clock.now() >= day_start else false()
    line_events = session.scalars(
        select(LineEvent).where(
            LineEvent.line_code == line.line_code,
            LineEvent.start_at < day_end,
            or_(still_open, LineEvent.end_at > day_start),
        ).order_by(LineEvent.start_at, LineEvent.id)
    )
    operator = current_row(session, line.line_code)
    return BoardOut(
        line_code=line.line_code,
        date=day,
        current_operator=current_operator_out(session, operator) if operator is not None else None,
        plans=plans,
        line_events=[line_event_out(session, e) for e in line_events],
        # TODO(要確認): ラインの進捗率の定義(今は その日の計画の生産数の合計 ÷ 計画数の合計)
        line_progress=_ratio(sum(x.produced_qty for x in plans), sum(x.plan.planned_qty for x in plans)),
        # TODO(要確認): 稼働率の定義
        utilization=None,
    )
