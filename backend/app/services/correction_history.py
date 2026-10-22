"""実績の訂正の履歴の取得(新しい順)。DBは読むだけ。詳細: docs/design/run-records.md"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import LineEvent, RunCorrection
from app.domain.workday import workday_of, workday_range
from app.services.kitting_plans import load_group
from app.services.masters import get_line
from app.services.views import CorrectionOut, correction_out

_NEWEST_FIRST = (RunCorrection.corrected_at.desc(), RunCorrection.id.desc())


def kitting_corrections(session: Session, kitting_no: str) -> list[CorrectionOut]:
    """計画のまとまり(キッティングNo.)の工程の記録の訂正。"""
    load_group(session, kitting_no)  # 無い計画なら 404
    rows = session.scalars(select(RunCorrection).where(RunCorrection.kitting_no == kitting_no).order_by(*_NEWEST_FIRST))
    return [correction_out(session, r) for r in rows]


def line_event_corrections(session: Session, line_code: str, day: dt.date | None, day_start: dt.time) -> list[CorrectionOut]:
    """ラインの付帯作業の訂正のうち、付帯作業の開始が稼働日(省略すると今の稼働日)にあるもの。"""
    line = get_line(session, line_code)
    day = day or workday_of(clock.now(), day_start)
    start, end = workday_range(day, day_start)
    rows = session.scalars(
        select(RunCorrection).join(LineEvent, LineEvent.id == RunCorrection.target_id)
        .where(RunCorrection.target_table == LineEvent.__tablename__, RunCorrection.line_code == line.line_code,
               LineEvent.start_at >= start, LineEvent.start_at < end)
        .order_by(*_NEWEST_FIRST)
    )
    return [correction_out(session, r) for r in rows]
