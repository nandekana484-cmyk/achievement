"""ライン画面と計画のAPIで使う、計画の絞り込み(開発指針 7.1)。キッティングNo.を返す。DBは読むだけ。

詳細: docs/design/line-screen.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session, aliased

from app.db.models import PLAN_ACTIVE, Plan, RunCompletion, RunEvent
from app.domain.workday import DISPLAY_MARGIN, display_range, workday_of, workday_range
from app.services.completions import valid_completion


def _overlaps(start: datetime, end: datetime):  # noqa: ANN202
    return and_(
        Plan.planned_start.is_not(None), Plan.planned_end.is_not(None),
        Plan.planned_start < end, Plan.planned_end > start,
    )


def kitting_nos_overlapping(session: Session, line_code: str, start: datetime, end: datetime) -> list[str]:
    """有効なロットの計画開始〜終了が start〜end と重なるキッティングNo.。"""
    stmt = select(Plan.kitting_no).distinct().where(
        Plan.line_code == line_code, Plan.status == PLAN_ACTIVE, _overlaps(start, end),
    )
    return list(session.scalars(stmt))


def _unfinished():  # noqa: ANN202
    """作業を始めたが片付けが終わっていない計画(取り消した記録は数えない)。"""
    started, cleanup = aliased(RunEvent), aliased(RunEvent)  # 呼び出し側が RunEvent を使っても、相関が混ざらないように別名にする
    return and_(
        exists().where(started.kitting_no == Plan.kitting_no, started.voided_at.is_(None)),
        not_(exists().where(RunCompletion.kitting_no == Plan.kitting_no, valid_completion(cleanup))),
    )


@dataclass(frozen=True)
class DisplayWindow:
    """ライン画面の表示範囲と、現場の画面で実績を直せる範囲(同じ)。stale_events は広げても範囲に入らない、終了のない記録。"""

    start: datetime
    end: datetime
    stale_events: tuple[RunEvent, ...]

    @property
    def stale_kitting_nos(self) -> tuple[str, ...]:
        return tuple(sorted({e.kitting_no for e in self.stale_events}))


def display_window(session: Session, line_code: str, day: date, day_start: time, max_extend_hours: int) -> DisplayWindow:
    """稼働日の前後12時間。そのラインに片付けが終わっていない計画があれば、始まりを一番古い最初の記録の12時間前まで広げる。

    広げるのは、稼働日の始まりの max_extend_hours 前まで。それより前に始まった終了のない記録は stale_events に入れる
    (ライン画面で警告し、管理画面の「終了していない古い記録」に出す)。詳細: docs/design/line-screen.md
    """
    start, end = display_range(day, day_start)
    rows = session.execute(
        select(RunEvent.kitting_no, func.min(RunEvent.start_at)).join(Plan, Plan.kitting_no == RunEvent.kitting_no)
        .where(Plan.line_code == line_code, Plan.status == PLAN_ACTIVE, RunEvent.voided_at.is_(None), _unfinished())
        .group_by(RunEvent.kitting_no)
    ).all()
    if rows:
        limit = workday_range(day, day_start)[0] - timedelta(hours=max_extend_hours)
        start = max(min(start, min(first for _, first in rows) - DISPLAY_MARGIN), limit)
    kittings = select(Plan.kitting_no).where(Plan.line_code == line_code, Plan.status == PLAN_ACTIVE)
    stale = session.scalars(select(RunEvent).where(
        RunEvent.kitting_no.in_(kittings), RunEvent.end_at.is_(None), RunEvent.voided_at.is_(None), RunEvent.start_at < start,
    ).order_by(RunEvent.start_at, RunEvent.id))
    return DisplayWindow(start, end, tuple(stale))


def line_of_kitting(session: Session, kitting_no: str) -> str | None:
    return session.scalars(select(Plan.line_code).where(Plan.kitting_no == kitting_no).limit(1)).first()


def board_kitting_nos(session: Session, line_code: str, display_start: datetime, display_end: datetime) -> list[str]:
    """ライン画面に出すキッティングNo.(取り消した計画は除く)。次のどれかに当てはまるもの。

    1. 計画開始〜終了が表示範囲と重なる(計画終了が過ぎて未着手のものも含む)
    2. 表示範囲の中に実績の記録がある(先行して始めた計画)
    3. 作業を始めたが、片付けが終わっていない(日付は問わない。遅れている計画)
    """
    events_in_range = exists().where(
        RunEvent.kitting_no == Plan.kitting_no, RunEvent.voided_at.is_(None), RunEvent.start_at < display_end,
        or_(RunEvent.end_at.is_(None), RunEvent.end_at > display_start),
    )
    stmt = select(Plan.kitting_no).distinct().where(
        Plan.line_code == line_code, Plan.status == PLAN_ACTIVE,
        or_(_overlaps(display_start, display_end), events_in_range, _unfinished()),
    )
    return list(session.scalars(stmt))


def stale_open_events(session: Session, now: datetime, day_start: time, max_extend_hours: int, line_code: str | None = None) -> list[RunEvent]:
    """表示範囲を広げても範囲に入らない、終了のない工程の記録(管理画面の「終了していない古い記録」)。開始の古い順。"""
    lines = [line_code] if line_code is not None else list(session.scalars(select(Plan.line_code).distinct().where(Plan.status == PLAN_ACTIVE)))
    found = [e for line in lines for e in display_window(session, line, workday_of(now, day_start), day_start, max_extend_hours).stale_events]
    return sorted(found, key=lambda e: (e.start_at, e.id))
