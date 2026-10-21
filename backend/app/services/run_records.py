"""回の工程の記録・備考・完了(開発指針 5.4、5.6、5.7)。キッティングNo.の単位。ルールの違反は RuleViolation(409)。

NG数は ng_inputs.py。詳細: docs/design/run-records.md
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PLAN_CANCELLED, Equipment, Reason, RunCompletion, RunEvent, RunInput
from app.domain.steps import InputKind, StepType
from app.services.errors import RuleViolation
from app.services.idempotency import run_idempotent
from app.services.kitting_plans import KittingGroup, load_group
from app.services.line_operators import resolve_recorder
from app.services.ng_inputs import latest_ng
from app.services.plan_views import lot_out
from app.services.views import RunInputOut, StepResultOut, run_completion_out, run_event_out, run_input_out


def _open_event(session: Session, kitting_no: str, step: StepType) -> RunEvent | None:
    return session.scalars(select(RunEvent).where(
        RunEvent.kitting_no == kitting_no, RunEvent.step_type == step.value, RunEvent.end_at.is_(None),
    )).first()


def _last_seq(session: Session, kitting_no: str, step: StepType) -> int:
    return session.scalar(select(func.max(RunEvent.seq)).where(
        RunEvent.kitting_no == kitting_no, RunEvent.step_type == step.value,
    )) or 0


def produced_total(session: Session, kitting_no: str) -> int:
    """生産の区切りの生産数の合計(終了した区切りだけ)。"""
    return session.scalar(select(func.coalesce(func.sum(RunEvent.produced_qty), 0)).where(
        RunEvent.kitting_no == kitting_no,
        RunEvent.step_type == StepType.PRODUCTION.value, RunEvent.end_at.is_not(None),
    )) or 0


def latest_completion(session: Session, kitting_no: str) -> RunCompletion | None:
    return session.scalars(select(RunCompletion).where(RunCompletion.kitting_no == kitting_no)
                           .order_by(RunCompletion.completed_at.desc(), RunCompletion.id.desc())).first()


def start_step(
    session: Session, kitting_no: str, step: StepType, request_id: str,
    restart_reason_id: int | None = None, operator_id: int | None = None, equipment_id: int | None = None,
) -> StepResultOut:
    payload = {"kitting_no": kitting_no, "step_type": step.value, "restart_reason_id": restart_reason_id,
               "operator_id": operator_id}
    if equipment_id is not None:
        payload["equipment_id"] = equipment_id

    def action(now: datetime) -> StepResultOut:
        group = load_group(session, kitting_no)
        if group.status == PLAN_CANCELLED:
            raise RuleViolation("取消になった計画は開始できません")
        if _open_event(session, kitting_no, step) is not None:
            raise RuleViolation(f"{step.label}は開始されたまま終了していません。先に終了してください")
        seq = _last_seq(session, kitting_no, step) + 1
        reason = _check_restart_reason(session, step, seq, restart_reason_id)
        _check_restart_equipment(session, group, reason, equipment_id)
        recorder = resolve_recorder(session, group.line_code, operator_id)

        event = RunEvent(
            kitting_no=kitting_no, step_type=step.value, seq=seq, start_at=now, started_by=recorder,
            restart_reason_id=restart_reason_id, equipment_id=equipment_id, start_request_id=request_id, created_at=now,
        )
        session.add(event)
        session.flush()
        return StepResultOut(event=run_event_out(session, event))

    return run_idempotent(session, request_id, "run.step.start", payload, StepResultOut, action)


def _check_restart_reason(session: Session, step: StepType, seq: int, reason_id: int | None) -> Reason | None:
    """再開理由を確かめ、2回目以降の生産の開始なら選んだ理由を返す。"""
    if step != StepType.PRODUCTION:
        if reason_id is not None:
            raise RuleViolation(f"{step.label}の開始では、再開理由は受け付けません")
        return None
    if seq == 1:
        if reason_id is not None:
            raise RuleViolation("1回目の生産の開始では、再開理由は受け付けません")
        return None
    if reason_id is None:
        raise RuleViolation("2回目以降の生産の開始では、再開理由を選んでください")
    reason = session.get(Reason, reason_id)
    if reason is None or not reason.active or not reason.usable_as_restart:
        raise RuleViolation("選んだ理由は、生産の再開理由として使えません")
    return reason


def _check_restart_equipment(session: Session, group: KittingGroup, reason: Reason | None, equipment_id: int | None) -> None:
    """設備は、設備が必要な再開理由を選んだときだけ受け付ける(任意。計画のラインの設備であること)。"""
    if equipment_id is None:
        return
    if reason is None or not reason.requires_equipment:
        raise RuleViolation("設備は、設備が必要な再開理由(マシントラブルなど)を選んだときだけ選べます")
    eq = session.get(Equipment, equipment_id)
    if eq is None or not eq.active or eq.line_code != group.line_code:
        raise RuleViolation("選んだ設備は、このラインの設備ではありません")


def end_step(
    session: Session, kitting_no: str, step: StepType, request_id: str,
    produced_qty: int | None = None, operator_id: int | None = None,
) -> StepResultOut:
    payload = {"kitting_no": kitting_no, "step_type": step.value, "produced_qty": produced_qty, "operator_id": operator_id}

    def action(now: datetime) -> StepResultOut:
        group = load_group(session, kitting_no)
        event = _open_event(session, kitting_no, step)
        if event is None:
            raise RuleViolation(f"{step.label}は開始されていません")
        _check_produced_qty(step, produced_qty)
        recorder = resolve_recorder(session, group.line_code, operator_id)

        event.end_at = now
        event.ended_by = recorder
        event.produced_qty = produced_qty
        event.end_request_id = request_id
        session.flush()

        completion = _complete(session, group, event, now) if step == StepType.CLEANUP else None
        return StepResultOut(
            event=run_event_out(session, event),
            completion=run_completion_out(completion) if completion is not None else None,
        )

    return run_idempotent(session, request_id, "run.step.end", payload, StepResultOut, action)


def _check_produced_qty(step: StepType, produced_qty: int | None) -> None:
    if step == StepType.PRODUCTION:
        if produced_qty is None:
            raise RuleViolation("生産の終了では、生産数を入力してください")
        if produced_qty < 0:
            raise RuleViolation("生産数は0以上の整数で入力してください")
    elif produced_qty is not None:
        raise RuleViolation(f"{step.label}の終了では、生産数は受け付けません")


def _complete(session: Session, group: KittingGroup, cleanup: RunEvent, now: datetime) -> RunCompletion:
    """片付けの終了 = その回の完了。その時点の計画数・想定タクト・ロットの一覧・NG数を写して残す。"""
    c = RunCompletion(
        kitting_no=group.kitting_no, cleanup_event_id=cleanup.id, completed_at=now,
        produced_qty=produced_total(session, group.kitting_no),
        plan_qty_snapshot=group.planned_qty, takt_sec_snapshot=group.takt_sec,
        lots_snapshot=json.dumps([lot_out(lot).model_dump() for lot in group.lots], ensure_ascii=False),
        ng_snapshot=json.dumps([n.model_dump(mode="json") for n in latest_ng(session, group.kitting_no)], ensure_ascii=False),
        # TODO(要確認): 稼働率の定義(定義が決まったらここで計算して保存する)
        utilization=None,
    )
    session.add(c)
    session.flush()
    return c


def add_remark(session: Session, kitting_no: str, text: str, request_id: str, operator_id: int | None = None) -> RunInputOut:
    payload = {"kitting_no": kitting_no, "text": text, "operator_id": operator_id}

    def action(now: datetime) -> RunInputOut:
        if not text.strip():
            raise RuleViolation("備考が空です")
        group = load_group(session, kitting_no)
        recorder = resolve_recorder(session, group.line_code, operator_id)
        row = RunInput(kitting_no=kitting_no, kind=InputKind.REMARK.value, value=text.strip(),
                       entered_by=recorder, entered_at=now, request_id=request_id)
        session.add(row)
        session.flush()
        return run_input_out(session, row)

    return run_idempotent(session, request_id, "run.remark", payload, RunInputOut, action)
