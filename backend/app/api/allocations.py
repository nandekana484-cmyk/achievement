"""ロットへの割り振りのAPI(現場の画面。生産記録票の印刷のページから使う)。

保存・元に戻すは作業者ID必須(operator_id / worker_id。省略するとそのラインの今の担当者)。詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.schemas import RequestId, _Recorder
from app.db.session import get_session
from app.services import field_side_link, lot_allocation
from app.services.kitting_plans import load_group
from app.services.lot_allocation import AllocationOut
from app.services.side_link_store import SOURCE_FIELD

router = APIRouter(prefix="/api", tags=["allocations"])


class AllocationSaveIn(_Recorder):
    request_id: RequestId
    quantities: dict[str, int] = Field(description="ロットNo. → 割り振る数(合計が生産数の合計と一致する)")


class AllocationResetIn(_Recorder):
    request_id: RequestId


@router.get("/runs/{kitting_no}/allocation", response_model=AllocationOut)
def get_allocation(
    kitting_no: str, balance_lot_no: str | None = Query(default=None, description="差を引くロット(提案の値を返す。保存しない)"),
    session: Session = Depends(get_session),
) -> AllocationOut:
    """今のロットへの割り振り。balance_lot_no を付けると、そのロットで差を調整した提案(0 未満なら proposal_error)。"""
    return lot_allocation.allocation_out(session, load_group(session, kitting_no), balance_lot_no)


@router.put("/runs/{kitting_no}/allocation", response_model=AllocationOut)
def save_allocation(kitting_no: str, body: AllocationSaveIn, session: Session = Depends(get_session)) -> AllocationOut:
    """割り振りを保存する(合計が生産数の合計と合わなければ 409)。"""
    actor = field_side_link.resolve_actor(session, kitting_no, body.operator_id, body.worker_id)
    return lot_allocation.save(session, actor, SOURCE_FIELD, kitting_no, body.quantities, body.request_id)


@router.post("/runs/{kitting_no}/allocation/reset", response_model=AllocationOut)
def reset_allocation(kitting_no: str, body: AllocationResetIn, session: Session = Depends(get_session)) -> AllocationOut:
    """保存した割り振りを外して、今の規則に戻す。"""
    actor = field_side_link.resolve_actor(session, kitting_no, body.operator_id, body.worker_id)
    return lot_allocation.reset(session, actor, SOURCE_FIELD, kitting_no, body.request_id)
