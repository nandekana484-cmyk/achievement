"""ライン画面と計画のAPIで使う、計画の絞り込み(開発指針 7.1)。DBは読むだけ。

詳細: docs/design/line-screen.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, exists, not_, or_, select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Plan, RunCompletion, RunEvent

_ORDER = (Plan.planned_start.is_(None), Plan.planned_start, Plan.kitting_no, Plan.lot_no)


def _overlaps(start: datetime, end: datetime):  # noqa: ANN202
    return and_(
        Plan.planned_start.is_not(None), Plan.planned_end.is_not(None),
        Plan.planned_start < end, Plan.planned_end > start,
    )


def plans_overlapping(session: Session, line_code: str, start: datetime, end: datetime) -> list[Plan]:
    """計画開始〜終了が start〜end と重なる有効な計画を、計画開始の順で返す。"""
    stmt = select(Plan).where(Plan.line_code == line_code, Plan.status == PLAN_ACTIVE, _overlaps(start, end))
    return list(session.scalars(stmt.order_by(*_ORDER)))


def board_plans(session: Session, line_code: str, display_start: datetime, display_end: datetime, now: datetime) -> list[Plan]:
    """ライン画面に出す有効な計画。次のどれかに当てはまるもの(計画終了が過ぎたのに未着手のものは除く)。

    1. 計画開始〜終了が表示範囲と重なる
    2. 表示範囲の中に実績の記録がある(先行して始めた計画)
    3. 作業を始めたが、片付けが終わっていない(日付は問わない。遅れている計画)
    """
    same_plan = and_(RunEvent.kitting_no == Plan.kitting_no, RunEvent.lot_no == Plan.lot_no)
    has_events = exists().where(same_plan)
    events_in_range = exists().where(
        same_plan, RunEvent.start_at < display_end,
        or_(RunEvent.end_at.is_(None), RunEvent.end_at > display_start),
    )
    completed = exists().where(RunCompletion.kitting_no == Plan.kitting_no, RunCompletion.lot_no == Plan.lot_no)
    in_range = and_(_overlaps(display_start, display_end), or_(has_events, Plan.planned_end >= now))
    stmt = select(Plan).where(
        Plan.line_code == line_code, Plan.status == PLAN_ACTIVE,
        or_(in_range, events_in_range, and_(has_events, not_(completed))),
    )
    return list(session.scalars(stmt.order_by(*_ORDER)))
