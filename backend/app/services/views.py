"""APIが返す形(Pydantic のモデル)と、DBの行からの組み立て。

冪等性のため、操作の応答はこの形のまま api_requests に保存し、再送にはそれを返す。
時刻はすべて日本時間(+09:00)付き。
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.models import (
    Equipment,
    Line,
    LineEvent,
    LineOperator,
    Operator,
    Plan,
    Reason,
    RunCompletion,
    RunEvent,
    RunInput,
)


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kitting_no: str
    lot_no: str
    file_no: str
    line_code: str
    product_name: str
    run_no: int
    planned_qty: int
    cumulative_qty: int | None
    order_qty: int | None
    planned_start: dt.datetime
    planned_end: dt.datetime
    deadline: dt.datetime | None
    issue_date: dt.date
    issue_seq: int
    legacy_status: str | None
    status: str
    takt_sec: float | None  # 想定タクト。単位は要確認(今は1枚あたりの秒と仮定)
    source_db: str | None  # 正とした既存アプリの月次DBのフォルダ名


# --- マスタ ---


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_code: str
    name: str
    sort_order: int


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_code: str
    name: str
    sort_order: int


class ReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str  # loss=ロス / non_loss=ロス以外
    counts_in_utilization: bool
    requires_equipment: bool
    requires_text: bool
    usable_as_line_event: bool
    usable_as_restart: bool
    sort_order: int


class MastersOut(BaseModel):
    lines: list[LineOut]
    operators: list[OperatorOut]
    equipment: list[EquipmentOut]
    reasons: list[ReasonOut]


# --- 実績 ---


class CurrentOperatorOut(BaseModel):
    line_code: str
    operator_id: int
    operator_name: str
    start_at: dt.datetime


class RunEventOut(BaseModel):
    id: int
    kitting_no: str
    lot_no: str
    step_type: str
    seq: int
    start_at: dt.datetime
    end_at: dt.datetime | None
    started_by: int
    started_by_name: str
    ended_by: int | None
    ended_by_name: str | None
    produced_qty: int | None
    restart_reason_id: int | None
    restart_reason_name: str | None
    # 再開理由の設備。既定値は、この項目が無かったころに保存した応答(api_requests)を読み直すため
    equipment_id: int | None = None
    equipment_name: str | None = None


class RunCompletionOut(BaseModel):
    id: int
    kitting_no: str
    lot_no: str
    completed_at: dt.datetime
    produced_qty: int
    ng_qty: int | None
    plan_qty_snapshot: int
    takt_sec_snapshot: float | None
    utilization: float | None  # 今は計算しない(稼働率の定義は要確認)


class StepResultOut(BaseModel):
    """工程の開始・終了の結果。片付けの終了では、作った完了の記録も返す。"""

    event: RunEventOut
    completion: RunCompletionOut | None = None


class RunInputOut(BaseModel):
    id: int
    kitting_no: str
    lot_no: str
    kind: str  # ng_qty / remark
    value: str
    entered_by: int
    entered_by_name: str
    entered_at: dt.datetime


class LineEventOut(BaseModel):
    id: int
    line_code: str
    reason_id: int
    reason_name: str
    equipment_id: int | None
    equipment_name: str | None
    reason_text: str | None
    start_at: dt.datetime
    end_at: dt.datetime | None
    started_by: int
    started_by_name: str
    ended_by: int | None
    ended_by_name: str | None


class BoardPlanOut(BaseModel):
    plan: PlanOut
    events: list[RunEventOut]  # 工程の記録(開始の順)
    produced_qty: int  # 生産の区切りの生産数の合計(終了したもの)
    ng_qty: int | None  # 最新のNG数
    completed: bool
    completion: RunCompletionOut | None  # 最新の完了
    progress: float | None  # 計画の進捗率 = 生産数の合計 ÷ 計画数(計画数が0なら null)


class BoardOut(BaseModel):
    line_code: str
    date: dt.date
    current_operator: CurrentOperatorOut | None
    plans: list[BoardPlanOut]
    line_events: list[LineEventOut]  # その日に重なる付帯作業
    # TODO(要確認): ラインの進捗率の定義(今は その日の計画の生産数の合計 ÷ 計画数の合計)
    line_progress: float | None
    utilization: float | None  # 今は計算しない(稼働率の定義は要確認)


# --- 組み立て ---


def _operator_name(session: Session, operator_id: int | None) -> str | None:
    if operator_id is None:
        return None
    op = session.get(Operator, operator_id)
    return op.name if op is not None else None


def current_operator_out(session: Session, row: LineOperator) -> CurrentOperatorOut:
    return CurrentOperatorOut(
        line_code=row.line_code, operator_id=row.operator_id,
        operator_name=_operator_name(session, row.operator_id) or "", start_at=row.start_at,
    )


def run_event_out(session: Session, e: RunEvent) -> RunEventOut:
    reason = session.get(Reason, e.restart_reason_id) if e.restart_reason_id is not None else None
    equipment = session.get(Equipment, e.equipment_id) if e.equipment_id is not None else None
    return RunEventOut(
        id=e.id, kitting_no=e.kitting_no, lot_no=e.lot_no, step_type=e.step_type, seq=e.seq,
        start_at=e.start_at, end_at=e.end_at,
        started_by=e.started_by, started_by_name=_operator_name(session, e.started_by) or "",
        ended_by=e.ended_by, ended_by_name=_operator_name(session, e.ended_by),
        produced_qty=e.produced_qty,
        restart_reason_id=e.restart_reason_id, restart_reason_name=reason.name if reason else None,
        equipment_id=e.equipment_id, equipment_name=equipment.name if equipment else None,
    )


def run_completion_out(c: RunCompletion) -> RunCompletionOut:
    return RunCompletionOut(
        id=c.id, kitting_no=c.kitting_no, lot_no=c.lot_no, completed_at=c.completed_at,
        produced_qty=c.produced_qty, ng_qty=c.ng_qty, plan_qty_snapshot=c.plan_qty_snapshot,
        takt_sec_snapshot=c.takt_sec_snapshot, utilization=c.utilization,
    )


def run_input_out(session: Session, i: RunInput) -> RunInputOut:
    return RunInputOut(
        id=i.id, kitting_no=i.kitting_no, lot_no=i.lot_no, kind=i.kind, value=i.value,
        entered_by=i.entered_by, entered_by_name=_operator_name(session, i.entered_by) or "",
        entered_at=i.entered_at,
    )


def line_event_out(session: Session, e: LineEvent) -> LineEventOut:
    reason = session.get(Reason, e.reason_id)
    equipment = session.get(Equipment, e.equipment_id) if e.equipment_id is not None else None
    return LineEventOut(
        id=e.id, line_code=e.line_code, reason_id=e.reason_id, reason_name=reason.name if reason else "",
        equipment_id=e.equipment_id, equipment_name=equipment.name if equipment else None,
        reason_text=e.reason_text, start_at=e.start_at, end_at=e.end_at,
        started_by=e.started_by, started_by_name=_operator_name(session, e.started_by) or "",
        ended_by=e.ended_by, ended_by_name=_operator_name(session, e.ended_by),
    )


def plan_out(p: Plan) -> PlanOut:
    return PlanOut.model_validate(p)


def line_out(line: Line) -> LineOut:
    return LineOut.model_validate(line)
