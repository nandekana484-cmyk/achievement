"""管理画面の「終了していない古い記録」: 表示範囲を広げても現場の画面に入らない、終了のない工程の記録を、管理者が直す。

直し方は2つ: 終了の時刻を入れる / 取り消す(取り消しの印。物理削除しない)。どちらも run_corrections(source=admin)と audit_log に残し、
片付けの終了で計画が完了になるときは、現場で片付けを終えたときと同じ完了の写しを作る。詳細: docs/design/run-records.md
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import Operator, Plan, RunCorrection, RunEvent
from app.db.session import write_transaction
from app.domain.corrections import CorrectionKind
from app.domain.steps import StepType
from app.services import audit
from app.services.completions import create_completion, rebuild_after_correction
from app.services.correction_rules import changes_of, check_reason, record_correction
from app.services.errors import NotFound, RuleViolation
from app.services.kitting_plans import load_group
from app.services.plan_query import stale_open_events
from app.services.run_corrections import _check_qty, _check_times


class OpenRunOut(BaseModel):
    id: int
    kitting_no: str
    line_code: str
    product_name: str
    step_type: str
    step_label: str
    start_at: dt.datetime
    started_by_name: str | None


class OpenRunResultOut(BaseModel):
    event_id: int
    kitting_no: str
    action: str  # "end" | "void"
    completed: bool  # 計画が完了になった(片付けの終了)、または完了の写しを作り直した


def _plan_of(session: Session, kitting_no: str) -> Plan | None:
    return session.scalars(select(Plan).where(Plan.kitting_no == kitting_no).limit(1)).first()


def list_open_runs(session: Session, day_start: dt.time, max_extend_hours: int, line_code: str | None = None) -> list[OpenRunOut]:
    out = []
    for e in stale_open_events(session, clock.now(), day_start, max_extend_hours, line_code):
        plan, starter = _plan_of(session, e.kitting_no), session.get(Operator, e.started_by)
        out.append(OpenRunOut(
            id=e.id, kitting_no=e.kitting_no, line_code=plan.line_code if plan else "", product_name=plan.product_name if plan else "",
            step_type=e.step_type, step_label=StepType(e.step_type).label, start_at=e.start_at,
            started_by_name=starter.name if starter else None,
        ))
    return out


def _target(session: Session, event_id: int, day_start: dt.time, max_extend_hours: int, now: dt.datetime) -> RunEvent:
    e = session.get(RunEvent, event_id)
    if e is None:
        raise NotFound(f"工程の記録(ID {event_id})が見つかりません")
    if not any(o.id == event_id for o in stale_open_events(session, now, day_start, max_extend_hours)):
        raise RuleViolation("この記録は、管理画面で直す対象ではありません(終了している・取り消している・現場の画面の範囲に入っている)")
    return e


def _record(session: Session, admin: Operator, e: RunEvent, kind: CorrectionKind, changes: list, reason: str,
            note: str | None, now: dt.datetime) -> RunCorrection:
    code, text = check_reason(reason, note)
    plan = _plan_of(session, e.kitting_no)
    return record_correction(
        session, target_table=RunEvent.__tablename__, target_id=e.id, kitting_no=e.kitting_no,
        line_code=plan.line_code if plan else "", kind=kind, changes=changes, reason=code, note=text,
        corrected_by=admin.id, now=now, scope=None, request_id=f"admin-{uuid.uuid4()}",  # scope=None = 管理画面(source=admin)
    )


def _complete(session: Session, e: RunEvent, correction_id: int) -> bool:
    """片付けの終了なら、現場で終えたときと同じ完了の写しを作る。それ以外は、完了済みの計画の写しを作り直す。"""
    if e.step_type == StepType.CLEANUP.value:
        create_completion(session, load_group(session, e.kitting_no), e)
        return True
    return rebuild_after_correction(session, e.kitting_no, correction_id) is not None


def end_open_run(
    session: Session, admin: Operator, event_id: int, end_at: dt.datetime, produced_qty: int | None, reason: str,
    note: str | None, day_start: dt.time, max_extend_hours: int,
) -> OpenRunResultOut:
    """終了の時刻を入れる(開始より後、今より前)。生産の区切りは良品数も要る。"""
    now = clock.now()
    check_reason(reason, note)
    with write_transaction(session):
        e = _target(session, event_id, day_start, max_extend_hours, now)
        step = StepType(e.step_type)
        _check_times(session, e.kitting_no, step, e.start_at, end_at, now, exclude_id=e.id)
        _check_qty(step, end_at, produced_qty)
        changes = changes_of({"end_at": None, "produced_qty": e.produced_qty}, {"end_at": end_at, "produced_qty": produced_qty})
        e.end_at, e.ended_by, e.produced_qty = end_at, admin.id, produced_qty
        session.flush()
        c = _record(session, admin, e, CorrectionKind.UPDATE, changes, reason, note, now)
        completed = _complete(session, e, c.id)
        audit.record_change(session, admin.id, "run_events", str(e.id), "admin_end_open_run", {"end_at": None},
                            {"end_at": end_at.isoformat(), "kitting_no": e.kitting_no}, reason=reason)
        session.commit()
    return OpenRunResultOut(event_id=e.id, kitting_no=e.kitting_no, action="end", completed=completed)


def void_open_run(
    session: Session, admin: Operator, event_id: int, reason: str, note: str | None, day_start: dt.time, max_extend_hours: int,
) -> OpenRunResultOut:
    """取り消す(行は消さず、取り消しの印を付ける)。"""
    now = clock.now()
    code, _ = check_reason(reason, note)
    with write_transaction(session):
        e = _target(session, event_id, day_start, max_extend_hours, now)
        e.voided_at, e.voided_by, e.void_reason = now, admin.id, code.value
        session.flush()
        c = _record(session, admin, e, CorrectionKind.VOID, changes_of({}, {"voided_at": now}), reason, note, now)
        completed = rebuild_after_correction(session, e.kitting_no, c.id) is not None
        audit.record_change(session, admin.id, "run_events", str(e.id), "admin_void_open_run", {"voided_at": None},
                            {"voided_at": now.isoformat(), "kitting_no": e.kitting_no}, reason=code.value)
        session.commit()
    return OpenRunResultOut(event_id=e.id, kitting_no=e.kitting_no, action="void", completed=completed)
