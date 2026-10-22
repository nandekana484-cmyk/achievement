"""付帯作業(開発指針 5.5)。計画には結びつけず、ラインに記録する。

詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Equipment, LineEvent, Reason
from app.services.errors import NotFound, RuleViolation
from app.services.idempotency import run_idempotent
from app.services.line_operators import resolve_recorder
from app.services.masters import get_line
from app.services.views import LineEventOut, line_event_out


def start_line_event(
    session: Session, line_code: str, reason_id: int, request_id: str,
    equipment_id: int | None = None, reason_text: str | None = None, operator_id: int | None = None,
) -> LineEventOut:
    line = get_line(session, line_code)
    payload = {"line_code": line.line_code, "reason_id": reason_id, "equipment_id": equipment_id,
               "reason_text": reason_text, "operator_id": operator_id}

    def action(now: datetime) -> LineEventOut:
        reason = session.get(Reason, reason_id)
        if reason is None or not reason.active or not reason.usable_as_line_event:
            raise RuleViolation("選んだ理由は、付帯作業として使えません")
        if equipment_id is not None:
            eq = session.get(Equipment, equipment_id)
            if eq is None or not eq.active or eq.line_code != line.line_code:
                raise RuleViolation("選んだ設備は、このラインの設備ではありません")
        elif reason.requires_equipment:
            raise RuleViolation(f"{reason.name}では、設備を選んでください")
        text = (reason_text or "").strip() or None
        if reason.requires_text and text is None:
            raise RuleViolation(f"{reason.name}では、理由を記入してください")
        opened = session.scalars(select(LineEvent).where(
            LineEvent.line_code == line.line_code, LineEvent.reason_id == reason_id, LineEvent.end_at.is_(None),
            LineEvent.voided_at.is_(None),
        )).first()
        if opened is not None:
            raise RuleViolation(f"{reason.name}は開始されたまま終了していません。先に終了してください")
        recorder = resolve_recorder(session, line.line_code, operator_id)

        event = LineEvent(
            line_code=line.line_code, reason_id=reason_id, equipment_id=equipment_id, reason_text=text,
            start_at=now, started_by=recorder, start_request_id=request_id,
        )
        session.add(event)
        session.flush()
        return line_event_out(session, event)

    return run_idempotent(session, request_id, "line_event.start", payload, LineEventOut, action)


def end_line_event(
    session: Session, line_code: str, event_id: int, request_id: str, operator_id: int | None = None,
) -> LineEventOut:
    line = get_line(session, line_code)
    payload = {"line_code": line.line_code, "event_id": event_id, "operator_id": operator_id}

    def action(now: datetime) -> LineEventOut:
        event = session.get(LineEvent, event_id)
        if event is None or event.line_code != line.line_code:
            raise NotFound(f"付帯作業(ID {event_id})が見つかりません")
        if event.voided_at is not None:
            raise RuleViolation("この付帯作業は取り消されています")
        if event.end_at is not None:
            raise RuleViolation("この付帯作業はすでに終了しています")
        recorder = resolve_recorder(session, line.line_code, operator_id)
        event.end_at = now
        event.ended_by = recorder
        event.end_request_id = request_id
        session.flush()
        return line_event_out(session, event)

    return run_idempotent(session, request_id, "line_event.end", payload, LineEventOut, action)
