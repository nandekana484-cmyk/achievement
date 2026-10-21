"""記録した人(作業者)の表示と、ラインの今の担当者の応答の形。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import LineOperator, Operator


class CurrentOperatorOut(BaseModel):
    line_code: str
    operator_id: int
    operator_name: str
    start_at: dt.datetime
    # 作業者ID。既定値は、この項目が無かったころに保存した応答(api_requests)を読み直すため(以下の *_worker_id も同じ)
    operator_worker_id: str | None = None


def operator_name(session: Session, operator_id: int | None) -> str | None:
    if operator_id is None:
        return None
    op = session.get(Operator, operator_id)
    return op.name if op is not None else None


def worker_id_of(session: Session, operator_id: int | None) -> str | None:
    """作業者ID(同じ名前の人を区別するため、名前の横に出す)。"""
    if operator_id is None:
        return None
    op = session.get(Operator, operator_id)
    return op.worker_id if op is not None else None


def current_operator_out(session: Session, row: LineOperator) -> CurrentOperatorOut:
    return CurrentOperatorOut(
        line_code=row.line_code, operator_id=row.operator_id,
        operator_name=operator_name(session, row.operator_id) or "", start_at=row.start_at,
        operator_worker_id=worker_id_of(session, row.operator_id),
    )
