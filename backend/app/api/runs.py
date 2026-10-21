"""回の工程の記録・NG数・備考のAPI。ルールは services/run_records.py。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NgQtyIn, RemarkIn, StepEndIn, StepStartIn
from app.db.session import get_session
from app.domain.steps import StepType
from app.services import run_records
from app.services.views import RunInputOut, StepResultOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.post("/{kitting_no}/{lot_no}/steps/{step_type}/start", response_model=StepResultOut)
def start_step(
    kitting_no: str, lot_no: str, step_type: StepType, body: StepStartIn, session: Session = Depends(get_session),
) -> StepResultOut:
    """工程を開始する。"""
    return run_records.start_step(
        session, kitting_no, lot_no, step_type, body.request_id,
        restart_reason_id=body.restart_reason_id, equipment_id=body.equipment_id, operator_id=body.operator_id,
    )


@router.post("/{kitting_no}/{lot_no}/steps/{step_type}/end", response_model=StepResultOut)
def end_step(
    kitting_no: str, lot_no: str, step_type: StepType, body: StepEndIn, session: Session = Depends(get_session),
) -> StepResultOut:
    """工程を終了する。片付けの終了では完了の記録も作る。"""
    return run_records.end_step(
        session, kitting_no, lot_no, step_type, body.request_id,
        produced_qty=body.produced_qty, operator_id=body.operator_id,
    )


@router.put("/{kitting_no}/{lot_no}/ng-qty", response_model=RunInputOut)
def set_ng_qty(kitting_no: str, lot_no: str, body: NgQtyIn, session: Session = Depends(get_session)) -> RunInputOut:
    """NG数を入力する(行を追加し、最新の値を有効とする)。"""
    return run_records.set_ng_qty(session, kitting_no, lot_no, body.ng_qty, body.request_id, operator_id=body.operator_id)


@router.post("/{kitting_no}/{lot_no}/remarks", response_model=RunInputOut)
def add_remark(kitting_no: str, lot_no: str, body: RemarkIn, session: Session = Depends(get_session)) -> RunInputOut:
    """備考を追加する。"""
    return run_records.add_remark(session, kitting_no, lot_no, body.text, body.request_id, operator_id=body.operator_id)
