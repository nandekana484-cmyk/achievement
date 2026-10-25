"""工程の記録(run_events)の訂正: 時刻と生産数の変更、取り消し、押し忘れの後からの追加(開発指針 5.4)。

記録は消さない。訂正のたびに run_corrections に1行残し、完了した計画なら完了の写しを作り直す。違反は RuleViolation(409)。
詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RunCorrection, RunEvent
from app.domain.corrections import CorrectionKind
from app.domain.steps import StepType
from app.services.completions import latest_completion, rebuild_after_correction
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
from app.services.kitting_plans import load_group
from app.services.line_operators import resolve_recorder
from app.services.run_records import next_seq
from app.services.views import RunCorrectionResultOut, correction_out, run_completion_out, run_event_out

EDITABLE_FIELDS = ("start_at", "end_at", "produced_qty")


def _event(session: Session, kitting_no: str, event_id: int) -> RunEvent:
    e = session.get(RunEvent, event_id)
    if e is None or e.kitting_no != kitting_no:
        raise NotFound(f"工程の記録(ID {event_id})が見つかりません")
    if e.voided_at is not None:
        raise RuleViolation("取り消した記録は直せません")
    return e


def _check_times(session: Session, kitting_no: str, step: StepType, start: datetime, end: datetime | None,
                 now: datetime, exclude_id: int | None) -> None:
    """開始 < 終了、未来は不可、同じ計画の生産の区切りどうしは重ならない、終了していない記録とは矛盾しない。"""
    check_order_and_future(start, end, now)
    others = session.scalars(select(RunEvent).where(
        RunEvent.kitting_no == kitting_no, RunEvent.step_type == step.value, RunEvent.voided_at.is_(None),
    ).order_by(RunEvent.start_at))
    for o in others:
        if o.id != exclude_id and conflicts(start, end, o.start_at, o.end_at, closed_may_overlap=step != StepType.PRODUCTION):
            what = "生産の区切り" if step == StepType.PRODUCTION else f"{step.label}の記録"
            raise RuleViolation(f"ほかの{what}({span_text(o.start_at, o.end_at)})と時間が重なります")


def _check_qty(step: StepType, end: datetime | None, qty: int | None) -> None:
    if step != StepType.PRODUCTION:
        if qty is not None:
            raise RuleViolation(f"{step.label}の記録には、良品数はありません")
        return
    if end is None:
        if qty is not None:
            raise RuleViolation("終了していない生産の区切りの良品数は、終了するときに入れてください")
        return
    if qty is None or qty < 0:
        raise RuleViolation("良品数は0以上の整数で入力してください")


def _result(session: Session, event: RunEvent, correction: RunCorrection) -> RunCorrectionResultOut:
    """訂正のあとの状態。完了した計画なら完了の写しを作り直す。"""
    rebuilt = rebuild_after_correction(session, event.kitting_no, correction.id)
    return RunCorrectionResultOut(
        correction=correction_out(session, correction), event=run_event_out(session, event),
        completed=latest_completion(session, event.kitting_no) is not None,
        completion=run_completion_out(rebuilt) if rebuilt is not None else None,
    )


def correct_run_event(
    session: Session, kitting_no: str, event_id: int, fields: dict[str, Any], reason: str, note: str | None,
    request_id: str, scope: FieldScope | None, operator_id: int | None = None,
) -> RunCorrectionResultOut:
    """開始・終了の時刻と、生産の区切りの生産数を直す。fields は直す項目だけ(EDITABLE_FIELDS)。"""
    payload = {"kitting_no": kitting_no, "event_id": event_id, "reason": reason, "note": note, "operator_id": operator_id,
               **{k: v.isoformat() if isinstance(v, datetime) else v for k, v in fields.items()}}

    def action(now: datetime) -> RunCorrectionResultOut:
        code, text = check_reason(reason, note)
        if not fields:
            raise RuleViolation("直す項目を指定してください")
        group = load_group(session, kitting_no)
        e = _event(session, kitting_no, event_id)
        if "end_at" in fields and e.end_at is None:
            raise RuleViolation("終了していない記録の終了の時刻は直せません。終了のボタンで終了してください")
        if fields.get("start_at", e.start_at) is None or (fields.get("end_at", e.end_at) is None and e.end_at is not None):
            raise RuleViolation("時刻は消せません。記録をなくすときは、取り消してください")
        check_record_in_scope(scope, now, e.start_at, e.end_at)
        check_new_times_in_scope(scope, now, [fields.get("start_at"), fields.get("end_at")])
        step = StepType(e.step_type)
        before = {k: getattr(e, k) for k in fields}
        start, end = fields.get("start_at", e.start_at), fields.get("end_at", e.end_at)
        _check_times(session, kitting_no, step, start, end, now, exclude_id=e.id)
        _check_qty(step, end, fields.get("produced_qty", e.produced_qty))
        changes = changes_of(before, fields)
        if not changes:
            raise RuleViolation("変更がありません")
        recorder = resolve_recorder(session, group.line_code, operator_id)
        for k, v in fields.items():
            setattr(e, k, v)
        session.flush()
        c = record_correction(session, target_table=RunEvent.__tablename__, target_id=e.id, kitting_no=kitting_no,
                              line_code=group.line_code, kind=CorrectionKind.UPDATE, changes=changes, reason=code, note=text,
                              corrected_by=recorder, now=now, scope=scope, request_id=request_id)
        return _result(session, e, c)

    return run_idempotent(session, request_id, "run.correct", payload, RunCorrectionResultOut, action)


def void_run_event(
    session: Session, kitting_no: str, event_id: int, reason: str, note: str | None,
    request_id: str, scope: FieldScope | None, operator_id: int | None = None,
) -> RunCorrectionResultOut:
    """記録を取り消す(行は消さず、取り消しの印を付ける)。片付けの終了を取り消すと、完了でなくなることがある。"""
    payload = {"kitting_no": kitting_no, "event_id": event_id, "reason": reason, "note": note, "operator_id": operator_id}

    def action(now: datetime) -> RunCorrectionResultOut:
        code, text = check_reason(reason, note)
        group = load_group(session, kitting_no)
        e = _event(session, kitting_no, event_id)
        check_record_in_scope(scope, now, e.start_at, e.end_at)
        recorder = resolve_recorder(session, group.line_code, operator_id)
        e.voided_at, e.voided_by, e.void_reason = now, recorder, code.value
        session.flush()
        c = record_correction(session, target_table=RunEvent.__tablename__, target_id=e.id, kitting_no=kitting_no,
                              line_code=group.line_code, kind=CorrectionKind.VOID,
                              changes=changes_of({}, {"voided_at": now}), reason=code, note=text,
                              corrected_by=recorder, now=now, scope=scope, request_id=request_id)
        return _result(session, e, c)

    return run_idempotent(session, request_id, "run.void", payload, RunCorrectionResultOut, action)


def add_run_event(
    session: Session, kitting_no: str, step: StepType, start_at: datetime, end_at: datetime, produced_qty: int | None,
    reason: str, note: str | None, request_id: str, scope: FieldScope | None, operator_id: int | None = None,
) -> RunCorrectionResultOut:
    """押し忘れた工程を後から記録する(開始と終了の両方。後から足した印を付ける)。"""
    payload = {"kitting_no": kitting_no, "step_type": step.value, "start_at": start_at.isoformat(),
               "end_at": end_at.isoformat(), "produced_qty": produced_qty, "reason": reason, "note": note,
               "operator_id": operator_id}

    def action(now: datetime) -> RunCorrectionResultOut:
        code, text = check_reason(reason, note)
        group = load_group(session, kitting_no)
        check_new_times_in_scope(scope, now, [start_at, end_at])
        _check_times(session, kitting_no, step, start_at, end_at, now, exclude_id=None)
        _check_qty(step, end_at, produced_qty)
        recorder = resolve_recorder(session, group.line_code, operator_id)
        e = RunEvent(
            kitting_no=kitting_no, step_type=step.value, seq=next_seq(session, kitting_no, step),
            start_at=start_at, end_at=end_at, started_by=recorder, ended_by=recorder, produced_qty=produced_qty,
            start_request_id=request_id, end_request_id=request_id, created_at=now, added_later=True,
        )
        session.add(e)
        session.flush()
        after = {"step_type": step.value, "start_at": start_at, "end_at": end_at}
        if produced_qty is not None:
            after["produced_qty"] = produced_qty
        c = record_correction(session, target_table=RunEvent.__tablename__, target_id=e.id, kitting_no=kitting_no,
                              line_code=group.line_code, kind=CorrectionKind.ADD, changes=changes_of({}, after),
                              reason=code, note=text, corrected_by=recorder, now=now, scope=scope, request_id=request_id)
        return _result(session, e, c)

    return run_idempotent(session, request_id, "run.add", payload, RunCorrectionResultOut, action)
