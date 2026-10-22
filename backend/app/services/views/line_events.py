"""付帯作業の応答の形と、DBの行からの組み立て。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Equipment, LineEvent, Reason
from app.services.views.operators import operator_name, worker_id_of


class LineEventOut(BaseModel):
    id: int
    line_code: str
    reason_id: int
    reason_name: str
    equipment_id: int | None
    equipment_name: str | None
    reason_text: str | None
    reason_name_vi: str | None = None  # 既定値は、この項目が無かったころに保存した応答を読み直すため
    equipment_name_vi: str | None = None
    start_at: dt.datetime
    end_at: dt.datetime | None
    started_by: int
    started_by_name: str
    ended_by: int | None
    ended_by_name: str | None
    started_by_worker_id: str | None = None
    ended_by_worker_id: str | None = None
    voided_at: dt.datetime | None = None  # 取り消し(タイムテーブルからは外し、履歴に出す)
    voided_by_name: str | None = None
    voided_by_worker_id: str | None = None
    void_reason: str | None = None


def line_event_out(session: Session, e: LineEvent) -> LineEventOut:
    reason = session.get(Reason, e.reason_id)
    equipment = session.get(Equipment, e.equipment_id) if e.equipment_id is not None else None
    return LineEventOut(
        id=e.id, line_code=e.line_code, reason_id=e.reason_id, reason_name=reason.name if reason else "",
        equipment_id=e.equipment_id, equipment_name=equipment.name if equipment else None,
        reason_name_vi=reason.name_vi if reason else None, equipment_name_vi=equipment.name_vi if equipment else None,
        reason_text=e.reason_text, start_at=e.start_at, end_at=e.end_at,
        started_by=e.started_by, started_by_name=operator_name(session, e.started_by) or "",
        ended_by=e.ended_by, ended_by_name=operator_name(session, e.ended_by),
        started_by_worker_id=worker_id_of(session, e.started_by), ended_by_worker_id=worker_id_of(session, e.ended_by),
        voided_at=e.voided_at, voided_by_name=operator_name(session, e.voided_by),
        voided_by_worker_id=worker_id_of(session, e.voided_by), void_reason=e.void_reason,
    )
