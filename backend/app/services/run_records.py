"""回の工程の記録・NG数と備考・完了(開発指針 5.4、5.6、5.7)。

ルール(違反は RuleViolation = 409。メッセージは画面にそのまま出せる文):
- 時刻はサーバーの clock.now()(開発指針 0-2)
- 記録者は operator_id の指定が無ければ、計画のラインの今の担当者
- 計画が無ければ NotFound。取消の計画は開始できない(終了はできる)
- 同じ計画の同じ工程で、終了していないものがあるのに開始はできない。終了していないものが無いのに終了はできない
- 生産の終了は生産数(0以上の整数)が必須。ほかの工程では受け付けない
- 生産の2回目以降の開始は再開理由が必須(生産の再開理由として使える理由だけ)。1回目とほかの工程では受け付けない
- 設備が必要な再開理由を選んだときは、設備を任意で受け付ける(計画のラインの設備)。それ以外では受け付けない
- 異なる工程どうしは、時間が重なってよい。生産の区切りの数に上限はない
- 片付けの終了で完了の記録を作る(やり直したらもう1件。最新のものを有効とする)。完了後も記録は受け付ける
- 記録は物理削除しない(開発指針 0-3)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PLAN_CANCELLED, Equipment, Plan, Reason, RunCompletion, RunEvent, RunInput
from app.domain.steps import InputKind, StepType
from app.services.errors import NotFound, RuleViolation
from app.services.idempotency import run_idempotent
from app.services.line_operators import resolve_recorder
from app.services.views import (
    RunInputOut,
    StepResultOut,
    run_completion_out,
    run_event_out,
    run_input_out,
)


def get_plan(session: Session, kitting_no: str, lot_no: str) -> Plan:
    plan = session.get(Plan, (kitting_no, lot_no))
    if plan is None:
        raise NotFound(f"計画(キッティングNo. {kitting_no}、ロットNo. {lot_no})が見つかりません")
    return plan


def _open_event(session: Session, plan: Plan, step: StepType) -> RunEvent | None:
    return session.scalars(select(RunEvent).where(
        RunEvent.kitting_no == plan.kitting_no, RunEvent.lot_no == plan.lot_no,
        RunEvent.step_type == step.value, RunEvent.end_at.is_(None),
    )).first()


def _last_seq(session: Session, plan: Plan, step: StepType) -> int:
    return session.scalar(select(func.max(RunEvent.seq)).where(
        RunEvent.kitting_no == plan.kitting_no, RunEvent.lot_no == plan.lot_no, RunEvent.step_type == step.value,
    )) or 0


def produced_total(session: Session, kitting_no: str, lot_no: str) -> int:
    """生産の区切りの生産数の合計(終了した区切りだけ)。"""
    return session.scalar(select(func.coalesce(func.sum(RunEvent.produced_qty), 0)).where(
        RunEvent.kitting_no == kitting_no, RunEvent.lot_no == lot_no,
        RunEvent.step_type == StepType.PRODUCTION.value, RunEvent.end_at.is_not(None),
    )) or 0


def latest_ng_qty(session: Session, kitting_no: str, lot_no: str) -> int | None:
    row = session.scalars(select(RunInput).where(
        RunInput.kitting_no == kitting_no, RunInput.lot_no == lot_no, RunInput.kind == InputKind.NG_QTY.value,
    ).order_by(RunInput.entered_at.desc(), RunInput.id.desc())).first()
    return int(row.value) if row is not None else None


def latest_completion(session: Session, kitting_no: str, lot_no: str) -> RunCompletion | None:
    return session.scalars(select(RunCompletion).where(
        RunCompletion.kitting_no == kitting_no, RunCompletion.lot_no == lot_no,
    ).order_by(RunCompletion.completed_at.desc(), RunCompletion.id.desc())).first()


def start_step(
    session: Session, kitting_no: str, lot_no: str, step: StepType, request_id: str,
    restart_reason_id: int | None = None, operator_id: int | None = None, equipment_id: int | None = None,
) -> StepResultOut:
    payload = {"kitting_no": kitting_no, "lot_no": lot_no, "step_type": step.value,
               "restart_reason_id": restart_reason_id, "operator_id": operator_id}
    if equipment_id is not None:  # 設備の項目が無かったころの要求と、同じ形のままにする
        payload["equipment_id"] = equipment_id

    def action(now: datetime) -> StepResultOut:
        plan = get_plan(session, kitting_no, lot_no)
        if plan.status == PLAN_CANCELLED:
            raise RuleViolation("取消になった計画は開始できません")
        if _open_event(session, plan, step) is not None:
            raise RuleViolation(f"{step.label}は開始されたまま終了していません。先に終了してください")
        seq = _last_seq(session, plan, step) + 1
        reason = _check_restart_reason(session, step, seq, restart_reason_id)
        _check_restart_equipment(session, plan, reason, equipment_id)
        recorder = resolve_recorder(session, plan.line_code, operator_id)

        event = RunEvent(
            kitting_no=plan.kitting_no, lot_no=plan.lot_no, step_type=step.value, seq=seq,
            start_at=now, started_by=recorder, restart_reason_id=restart_reason_id, equipment_id=equipment_id,
            start_request_id=request_id, created_at=now,
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


def _check_restart_equipment(session: Session, plan: Plan, reason: Reason | None, equipment_id: int | None) -> None:
    """設備は、設備が必要な再開理由を選んだときだけ受け付ける(任意。計画のラインの設備であること)。"""
    if equipment_id is None:
        return
    if reason is None or not reason.requires_equipment:
        raise RuleViolation("設備は、設備が必要な再開理由(マシントラブルなど)を選んだときだけ選べます")
    eq = session.get(Equipment, equipment_id)
    if eq is None or not eq.active or eq.line_code != plan.line_code:
        raise RuleViolation("選んだ設備は、このラインの設備ではありません")


def end_step(
    session: Session, kitting_no: str, lot_no: str, step: StepType, request_id: str,
    produced_qty: int | None = None, operator_id: int | None = None,
) -> StepResultOut:
    payload = {"kitting_no": kitting_no, "lot_no": lot_no, "step_type": step.value,
               "produced_qty": produced_qty, "operator_id": operator_id}

    def action(now: datetime) -> StepResultOut:
        plan = get_plan(session, kitting_no, lot_no)
        event = _open_event(session, plan, step)
        if event is None:
            raise RuleViolation(f"{step.label}は開始されていません")
        if step == StepType.PRODUCTION:
            if produced_qty is None:
                raise RuleViolation("生産の終了では、生産数を入力してください")
            if produced_qty < 0:
                raise RuleViolation("生産数は0以上の整数で入力してください")
        elif produced_qty is not None:
            raise RuleViolation(f"{step.label}の終了では、生産数は受け付けません")
        recorder = resolve_recorder(session, plan.line_code, operator_id)

        event.end_at = now
        event.ended_by = recorder
        event.produced_qty = produced_qty
        event.end_request_id = request_id
        session.flush()

        completion = None
        if step == StepType.CLEANUP:
            completion = _complete(session, plan, event, now)
        return StepResultOut(
            event=run_event_out(session, event),
            completion=run_completion_out(completion) if completion is not None else None,
        )

    return run_idempotent(session, request_id, "run.step.end", payload, StepResultOut, action)


def _complete(session: Session, plan: Plan, cleanup: RunEvent, now: datetime) -> RunCompletion:
    """片付けの終了 = その回の完了。その時点の計画数と想定タクトを写して残す(後で計画が変わっても変えない)。"""
    c = RunCompletion(
        kitting_no=plan.kitting_no, lot_no=plan.lot_no, cleanup_event_id=cleanup.id, completed_at=now,
        produced_qty=produced_total(session, plan.kitting_no, plan.lot_no),
        ng_qty=latest_ng_qty(session, plan.kitting_no, plan.lot_no),
        plan_qty_snapshot=plan.planned_qty, takt_sec_snapshot=plan.takt_sec,
        # TODO(要確認): 稼働率の定義(定義が決まったらここで計算して保存する)
        utilization=None,
    )
    session.add(c)
    session.flush()
    return c


def set_ng_qty(
    session: Session, kitting_no: str, lot_no: str, ng_qty: int, request_id: str, operator_id: int | None = None,
) -> RunInputOut:
    """NG数を入力する。行を追加し、最新の値を有効とする。"""
    payload = {"kitting_no": kitting_no, "lot_no": lot_no, "ng_qty": ng_qty, "operator_id": operator_id}

    def action(now: datetime) -> RunInputOut:
        if ng_qty < 0:
            raise RuleViolation("NG数は0以上の整数で入力してください")
        return _add_input(session, kitting_no, lot_no, InputKind.NG_QTY, str(ng_qty), request_id, operator_id, now)

    return run_idempotent(session, request_id, "run.ng_qty", payload, RunInputOut, action)


def add_remark(
    session: Session, kitting_no: str, lot_no: str, text: str, request_id: str, operator_id: int | None = None,
) -> RunInputOut:
    payload = {"kitting_no": kitting_no, "lot_no": lot_no, "text": text, "operator_id": operator_id}

    def action(now: datetime) -> RunInputOut:
        if not text.strip():
            raise RuleViolation("備考が空です")
        return _add_input(session, kitting_no, lot_no, InputKind.REMARK, text.strip(), request_id, operator_id, now)

    return run_idempotent(session, request_id, "run.remark", payload, RunInputOut, action)


def _add_input(
    session: Session, kitting_no: str, lot_no: str, kind: InputKind, value: str,
    request_id: str, operator_id: int | None, now: datetime,
) -> RunInputOut:
    plan = get_plan(session, kitting_no, lot_no)
    recorder = resolve_recorder(session, plan.line_code, operator_id)
    row = RunInput(kitting_no=plan.kitting_no, lot_no=plan.lot_no, kind=kind.value, value=value,
                   entered_by=recorder, entered_at=now, request_id=request_id)
    session.add(row)
    session.flush()
    return run_input_out(session, row)
