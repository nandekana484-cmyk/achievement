"""回の工程の記録・NG数・備考のAPI(キッティングNo.の単位)。ルールは services/run_records.py と ng_inputs.py。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NgQtyIn, RemarkIn, StepEndIn, StepStartIn, _Recorder
from app.db.session import get_session
from app.domain.steps import StepType
from app.services import board, masters, ng_inputs, run_records
from app.services.plan_views import BoardPlanOut
from app.services.views import NgInputOut, RunInputOut, StepResultOut

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _recorder(session: Session, body: _Recorder) -> int | None:
    """記録者の指定(operator_id か worker_id)を、本アプリの中の番号にする。"""
    return masters.resolve_operator_ref(session, body.operator_id, body.worker_id)


@router.get("/{kitting_no}", response_model=BoardPlanOut)
def get_run(kitting_no: str, session: Session = Depends(get_session)) -> BoardPlanOut:
    """計画のまとまり1件の工程の記録・生産数・NG数・完了・進捗率(表示範囲の外の計画を選んだときに使う)。"""
    return board.get_run(session, kitting_no)


@router.post("/{kitting_no}/steps/{step_type}/start", response_model=StepResultOut)
def start_step(kitting_no: str, step_type: StepType, body: StepStartIn, session: Session = Depends(get_session)) -> StepResultOut:
    """工程を開始する。"""
    return run_records.start_step(
        session, kitting_no, step_type, body.request_id,
        restart_reason_id=body.restart_reason_id, equipment_id=body.equipment_id, operator_id=_recorder(session, body),
    )


@router.post("/{kitting_no}/steps/{step_type}/end", response_model=StepResultOut)
def end_step(kitting_no: str, step_type: StepType, body: StepEndIn, session: Session = Depends(get_session)) -> StepResultOut:
    """工程を終了する。片付けの終了では完了の記録も作る。"""
    return run_records.end_step(
        session, kitting_no, step_type, body.request_id, produced_qty=body.produced_qty, operator_id=_recorder(session, body),
    )


@router.put("/{kitting_no}/ng-qty", response_model=NgInputOut)
def set_ng_qty(kitting_no: str, body: NgQtyIn, session: Session = Depends(get_session)) -> NgInputOut:
    """NG数を、ロットとNGが出た面を選んで入力する(同じロット・面では最新の値を有効とする)。"""
    return ng_inputs.set_ng_qty(session, kitting_no, body.lot_no, body.side, body.ng_qty, body.request_id,
                                operator_id=_recorder(session, body))


@router.post("/{kitting_no}/remarks", response_model=RunInputOut)
def add_remark(kitting_no: str, body: RemarkIn, session: Session = Depends(get_session)) -> RunInputOut:
    """備考を追加する。"""
    return run_records.add_remark(session, kitting_no, body.text, body.request_id, operator_id=_recorder(session, body))
