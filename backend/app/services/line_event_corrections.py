"""付帯作業(line_events)の訂正: 開始・終了の時刻、理由(設備・記入)の変更と、取り消し(開発指針 5.5)。

記録は消さない。訂正のたびに run_corrections に1行残す。違反は RuleViolation(409)。詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Equipment, LineEvent, Reason
from app.domain.corrections import CorrectionKind
from app.services.correction_rules import (
    FieldScope,
    changes_of,
    check_new_times_in_scope,
    check_order_and_future,
    check_reason,
    check_record_in_scope,
    conflicts,
    record_correction,
    span_text,
)
from app.services.errors import NotFound, RuleViolation
from app.services.idempotency import run_idempotent
from app.services.line_operators import resolve_recorder
from app.services.masters import get_line
from app.services.views import LineEventCorrectionResultOut, correction_out, line_event_out

EDITABLE_FIELDS = ("start_at", "end_at", "reason_id", "equipment_id", "reason_text")


def _event(session: Session, line_code: str, event_id: int) -> LineEvent:
    e = session.get(LineEvent, event_id)
    if e is None or e.line_code != line_code:
        raise NotFound(f"付帯作業(ID {event_id})が見つかりません")
    if e.voided_at is not None:
        raise RuleViolation("取り消した付帯作業は直せません")
    return e


def _normalized(fields: dict[str, Any]) -> dict[str, Any]:
    """理由の記入は前後の空白を除き、空なら無しにする。"""
    out = dict(fields)
    if "reason_text" in out:
        out["reason_text"] = (out["reason_text"] or "").strip() or None
    return out


def _check_reason_fields(session: Session, e: LineEvent, after: dict[str, Any]) -> None:
    """付帯作業として使える理由か、設備・記入が必要な理由ならそれがあるか(開始のときと同じルール)。"""
    reason_id = after.get("reason_id", e.reason_id)
    reason = session.get(Reason, reason_id)
    if "reason_id" in after and reason_id != e.reason_id and (
            reason is None or not reason.active or not reason.usable_as_line_event):
        raise RuleViolation("選んだ理由は、付帯作業として使えません")
    equipment_id = after.get("equipment_id", e.equipment_id)
    if equipment_id is not None and "equipment_id" in after and equipment_id != e.equipment_id:
        eq = session.get(Equipment, equipment_id)
        if eq is None or not eq.active or eq.line_code != e.line_code:
            raise RuleViolation("選んだ設備は、このラインの設備ではありません")
    if reason is not None and reason.requires_equipment and equipment_id is None:
        raise RuleViolation(f"{reason.name}では、設備を選んでください")
    if reason is not None and reason.requires_text and after.get("reason_text", e.reason_text) is None:
        raise RuleViolation(f"{reason.name}では、理由を記入してください")


def _check_times(session: Session, e: LineEvent, start: datetime, end: datetime | None, reason_id: int, now: datetime) -> None:
    """開始 < 終了、未来は不可。同じ理由の付帯作業のうち、終了していない記録とは重ならない。"""
    check_order_and_future(start, end, now)
    others = session.scalars(select(LineEvent).where(
        LineEvent.line_code == e.line_code, LineEvent.reason_id == reason_id, LineEvent.voided_at.is_(None),
        LineEvent.id != e.id,
    ))
    for o in others:
        if conflicts(start, end, o.start_at, o.end_at, closed_may_overlap=True):
            raise RuleViolation(f"同じ理由の付帯作業({span_text(o.start_at, o.end_at)})と時間が重なります")


def correct_line_event(
    session: Session, line_code: str, event_id: int, fields: dict[str, Any], reason: str, note: str | None,
    request_id: str, scope: FieldScope | None, operator_id: int | None = None,
) -> LineEventCorrectionResultOut:
    """付帯作業の時刻・理由・設備・記入を直す。fields は直す項目だけ(EDITABLE_FIELDS)。"""
    line = get_line(session, line_code)
    payload = {"line_code": line.line_code, "event_id": event_id, "reason": reason, "note": note, "operator_id": operator_id,
               **{k: v.isoformat() if isinstance(v, datetime) else v for k, v in fields.items()}}

    def action(now: datetime) -> LineEventCorrectionResultOut:
        code, text = check_reason(reason, note)
        if not fields:
            raise RuleViolation("直す項目を指定してください")
        e = _event(session, line.line_code, event_id)
        after = _normalized(fields)
        if "end_at" in after and e.end_at is None:
            raise RuleViolation("終了していない付帯作業の終了の時刻は直せません。終了のボタンで終了してください")
        if after.get("start_at", e.start_at) is None or (after.get("end_at", e.end_at) is None and e.end_at is not None):
            raise RuleViolation("時刻は消せません。記録をなくすときは、取り消してください")
        if after.get("reason_id", e.reason_id) is None:
            raise RuleViolation("付帯作業の理由を選んでください")
        check_record_in_scope(scope, now, e.start_at, e.end_at)
        check_new_times_in_scope(scope, now, [after.get("start_at"), after.get("end_at")])
        _check_reason_fields(session, e, after)
        _check_times(session, e, after.get("start_at", e.start_at), after.get("end_at", e.end_at),
                     after.get("reason_id", e.reason_id), now)
        changes = changes_of({k: getattr(e, k) for k in after}, after)
        if not changes:
            raise RuleViolation("変更がありません")
        recorder = resolve_recorder(session, line.line_code, operator_id)
        for k, v in after.items():
            setattr(e, k, v)
        session.flush()
        c = record_correction(session, target_table=LineEvent.__tablename__, target_id=e.id, kitting_no=None,
                              line_code=line.line_code, kind=CorrectionKind.UPDATE, changes=changes, reason=code,
                              note=text, corrected_by=recorder, now=now, scope=scope, request_id=request_id)
        return LineEventCorrectionResultOut(correction=correction_out(session, c), event=line_event_out(session, e))

    return run_idempotent(session, request_id, "line_event.correct", payload, LineEventCorrectionResultOut, action)


def void_line_event(
    session: Session, line_code: str, event_id: int, reason: str, note: str | None,
    request_id: str, scope: FieldScope | None, operator_id: int | None = None,
) -> LineEventCorrectionResultOut:
    """付帯作業を取り消す(行は消さず、取り消しの印を付ける)。"""
    line = get_line(session, line_code)
    payload = {"line_code": line.line_code, "event_id": event_id, "reason": reason, "note": note, "operator_id": operator_id}

    def action(now: datetime) -> LineEventCorrectionResultOut:
        code, text = check_reason(reason, note)
        e = _event(session, line.line_code, event_id)
        check_record_in_scope(scope, now, e.start_at, e.end_at)
        recorder = resolve_recorder(session, line.line_code, operator_id)
        e.voided_at, e.voided_by, e.void_reason = now, recorder, code.value
        session.flush()
        c = record_correction(session, target_table=LineEvent.__tablename__, target_id=e.id, kitting_no=None,
                              line_code=line.line_code, kind=CorrectionKind.VOID, changes=changes_of({}, {"voided_at": now}),
                              reason=code, note=text, corrected_by=recorder, now=now, scope=scope, request_id=request_id)
        return LineEventCorrectionResultOut(correction=correction_out(session, c), event=line_event_out(session, e))

    return run_idempotent(session, request_id, "line_event.void", payload, LineEventCorrectionResultOut, action)
