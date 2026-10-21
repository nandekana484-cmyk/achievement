"""ラインの今の担当者(開発指針 5.6)。

- ラインごとに「今の担当者」を1人持つ。交代すると前の行に end_at を入れ、新しい行を足す(行は消さない)
- ボタン操作の記録者は、operator_id の指定が無ければラインの今の担当者。どちらも無ければ記録できない
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LineOperator
from app.services.errors import RuleViolation
from app.services.idempotency import run_idempotent
from app.services.masters import get_active_operator, get_line
from app.services.views import CurrentOperatorOut, current_operator_out

NO_OPERATOR = "担当者が設定されていません"


def current_row(session: Session, line_code: str) -> LineOperator | None:
    return session.scalars(
        select(LineOperator).where(LineOperator.line_code == line_code, LineOperator.end_at.is_(None))
    ).first()


def get_current_operator(session: Session, line_code: str) -> CurrentOperatorOut | None:
    line = get_line(session, line_code)
    row = current_row(session, line.line_code)
    return current_operator_out(session, row) if row is not None else None


def resolve_recorder(session: Session, line_code: str, operator_id: int | None) -> int:
    """記録者を決める。指定が無ければ、ラインの今の担当者。"""
    if operator_id is not None:
        return get_active_operator(session, operator_id).id
    row = current_row(session, line_code)
    if row is None:
        raise RuleViolation(NO_OPERATOR)
    return row.operator_id


def change_operator(session: Session, line_code: str, operator_id: int, request_id: str) -> CurrentOperatorOut:
    """今の担当者を交代する。すでに同じ人が担当者なら、何も変えずに今の担当者を返す。"""
    line = get_line(session, line_code)
    payload = {"line_code": line.line_code, "operator_id": operator_id}

    def action(now: datetime) -> CurrentOperatorOut:
        get_active_operator(session, operator_id)
        row = current_row(session, line.line_code)
        if row is not None and row.operator_id == operator_id:
            return current_operator_out(session, row)
        if row is not None:
            row.end_at = now
            session.flush()  # 「今の担当者は1人」の一意制約に当たらないよう、先に前の行を閉じる
        new = LineOperator(line_code=line.line_code, operator_id=operator_id, start_at=now, request_id=request_id)
        session.add(new)
        session.flush()
        return current_operator_out(session, new)

    return run_idempotent(session, request_id, "line_operator.change", payload, CurrentOperatorOut, action)
