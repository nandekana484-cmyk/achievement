"""APIが返す形(Pydantic のモデル)と、DBの行からの組み立て。

冪等性のため、操作の応答はこの形のまま api_requests に保存し、再送にはそれを返す。
時刻はすべて日本時間(+09:00)付き。
"""

from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.models import (
    Equipment,
    Line,
    LineEvent,
    LineOperator,
    Operator,
    Reason,
    RunCompletion,
    RunEvent,
    RunInput,
    RunNgInput,
)


# --- マスタ ---


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_code: str
    name: str
    sort_order: int


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # 本アプリの中の番号
    name: str
    worker_id: str | None  # 作業者ID(既存アプリの表記のまま)。同じ名前の人を区別するため、名前の横に出す
    role: str
    sort_order: int


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_code: str
    name: str
    name_vi: str | None = None  # ベトナム語の名前(空なら画面は name を出す)
    sort_order: int


class ReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_vi: str | None = None  # ベトナム語の名前(空なら画面は name を出す)
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
    # 作業者ID。既定値は、この項目が無かったころに保存した応答(api_requests)を読み直すため(以下の *_worker_id も同じ)
    operator_worker_id: str | None = None


class RunEventOut(BaseModel):
    id: int
    kitting_no: str
    step_type: str
    seq: int
    start_at: dt.datetime
    end_at: dt.datetime | None
    started_by: int
    started_by_name: str
    ended_by: int | None
    ended_by_name: str | None
    started_by_worker_id: str | None = None
    ended_by_worker_id: str | None = None
    produced_qty: int | None
    restart_reason_id: int | None
    restart_reason_name: str | None
    # 再開理由の設備。既定値は、この項目が無かったころに保存した応答(api_requests)を読み直すため
    equipment_id: int | None = None
    equipment_name: str | None = None
    restart_reason_name_vi: str | None = None
    equipment_name_vi: str | None = None


class LotOut(BaseModel):
    """まとまり(キッティングNo.)の中のロット(確認用)。"""

    lot_no: str
    product_name: str  # 基板名
    planned_qty: int


class NgEntryOut(BaseModel):
    """ロットと面ごとの、最新のNG数。"""

    lot_no: str
    side: int  # NGが出た面
    side_kitting_no: str  # NGが出た面の計画のキッティングNo.
    ng_qty: int
    entered_by_name: str = ""
    entered_at: dt.datetime | None = None
    entered_by_worker_id: str | None = None


class RunCompletionOut(BaseModel):
    id: int
    kitting_no: str
    completed_at: dt.datetime
    produced_qty: int
    plan_qty_snapshot: int  # ロットの数量の合計
    takt_sec_snapshot: float | None
    lots_snapshot: list[LotOut]
    ng_snapshot: list[NgEntryOut]
    utilization: float | None  # 今は計算しない(稼働率の定義は要確認)


class StepResultOut(BaseModel):
    """工程の開始・終了の結果。片付けの終了では、作った完了の記録も返す。"""

    event: RunEventOut
    completion: RunCompletionOut | None = None


class RunInputOut(BaseModel):
    """備考(キッティングNo.の単位)。"""

    id: int
    kitting_no: str
    kind: str  # remark
    value: str
    entered_by: int
    entered_by_name: str
    entered_at: dt.datetime
    entered_by_worker_id: str | None = None


class NgInputOut(BaseModel):
    """NG数の入力の結果。"""

    id: int
    kitting_no: str  # 入力した画面の計画
    lot_no: str
    side: int
    side_kitting_no: str
    ng_qty: int
    entered_by: int
    entered_by_name: str
    entered_at: dt.datetime
    entered_by_worker_id: str | None = None


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


# --- 組み立て ---


def _operator_name(session: Session, operator_id: int | None) -> str | None:
    if operator_id is None:
        return None
    op = session.get(Operator, operator_id)
    return op.name if op is not None else None


def _worker_id(session: Session, operator_id: int | None) -> str | None:
    """作業者ID(同じ名前の人を区別するため、名前の横に出す)。"""
    if operator_id is None:
        return None
    op = session.get(Operator, operator_id)
    return op.worker_id if op is not None else None


def current_operator_out(session: Session, row: LineOperator) -> CurrentOperatorOut:
    return CurrentOperatorOut(
        line_code=row.line_code, operator_id=row.operator_id,
        operator_name=_operator_name(session, row.operator_id) or "", start_at=row.start_at,
        operator_worker_id=_worker_id(session, row.operator_id),
    )


def run_event_out(session: Session, e: RunEvent) -> RunEventOut:
    reason = session.get(Reason, e.restart_reason_id) if e.restart_reason_id is not None else None
    equipment = session.get(Equipment, e.equipment_id) if e.equipment_id is not None else None
    return RunEventOut(
        id=e.id, kitting_no=e.kitting_no, step_type=e.step_type, seq=e.seq,
        start_at=e.start_at, end_at=e.end_at,
        started_by=e.started_by, started_by_name=_operator_name(session, e.started_by) or "",
        ended_by=e.ended_by, ended_by_name=_operator_name(session, e.ended_by),
        started_by_worker_id=_worker_id(session, e.started_by), ended_by_worker_id=_worker_id(session, e.ended_by),
        produced_qty=e.produced_qty,
        restart_reason_id=e.restart_reason_id, restart_reason_name=reason.name if reason else None,
        equipment_id=e.equipment_id, equipment_name=equipment.name if equipment else None,
        restart_reason_name_vi=reason.name_vi if reason else None, equipment_name_vi=equipment.name_vi if equipment else None,
    )


def run_completion_out(c: RunCompletion) -> RunCompletionOut:
    return RunCompletionOut(
        id=c.id, kitting_no=c.kitting_no, completed_at=c.completed_at,
        produced_qty=c.produced_qty, plan_qty_snapshot=c.plan_qty_snapshot, takt_sec_snapshot=c.takt_sec_snapshot,
        lots_snapshot=[LotOut(**x) for x in json.loads(c.lots_snapshot or "[]")],
        ng_snapshot=[NgEntryOut(**x) for x in json.loads(c.ng_snapshot or "[]")],
        utilization=c.utilization,
    )


def run_input_out(session: Session, i: RunInput) -> RunInputOut:
    return RunInputOut(
        id=i.id, kitting_no=i.kitting_no, kind=i.kind, value=i.value,
        entered_by=i.entered_by, entered_by_name=_operator_name(session, i.entered_by) or "",
        entered_at=i.entered_at, entered_by_worker_id=_worker_id(session, i.entered_by),
    )


def ng_entry_out(session: Session, n: RunNgInput) -> NgEntryOut:
    return NgEntryOut(
        lot_no=n.lot_no, side=n.side, side_kitting_no=n.side_kitting_no, ng_qty=n.ng_qty,
        entered_by_name=_operator_name(session, n.entered_by) or "", entered_at=n.entered_at,
        entered_by_worker_id=_worker_id(session, n.entered_by),
    )


def ng_input_out(session: Session, n: RunNgInput) -> NgInputOut:
    return NgInputOut(
        id=n.id, kitting_no=n.kitting_no, lot_no=n.lot_no, side=n.side, side_kitting_no=n.side_kitting_no,
        ng_qty=n.ng_qty, entered_by=n.entered_by, entered_by_name=_operator_name(session, n.entered_by) or "",
        entered_at=n.entered_at, entered_by_worker_id=_worker_id(session, n.entered_by),
    )


def line_event_out(session: Session, e: LineEvent) -> LineEventOut:
    reason = session.get(Reason, e.reason_id)
    equipment = session.get(Equipment, e.equipment_id) if e.equipment_id is not None else None
    return LineEventOut(
        id=e.id, line_code=e.line_code, reason_id=e.reason_id, reason_name=reason.name if reason else "",
        equipment_id=e.equipment_id, equipment_name=equipment.name if equipment else None,
        reason_name_vi=reason.name_vi if reason else None, equipment_name_vi=equipment.name_vi if equipment else None,
        reason_text=e.reason_text, start_at=e.start_at, end_at=e.end_at,
        started_by=e.started_by, started_by_name=_operator_name(session, e.started_by) or "",
        ended_by=e.ended_by, ended_by_name=_operator_name(session, e.ended_by),
        started_by_worker_id=_worker_id(session, e.started_by), ended_by_worker_id=_worker_id(session, e.ended_by),
    )


def line_out(line: Line) -> LineOut:
    return LineOut.model_validate(line)
