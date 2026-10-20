"""計画と、計画の同期状況のAPI。"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_ACTIVE, Plan, PlanSyncRun, PlanSyncWarning
from app.db.session import get_session

router = APIRouter(prefix="/api", tags=["plans"])


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


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: dt.datetime
    finished_at: dt.datetime
    result: str
    added: int
    revived: int  # 取消から復活した計画
    changed: int
    unchanged: int
    cancelled: int
    error_message: str | None


class SyncStatusOut(BaseModel):
    last_run: SyncRunOut | None
    warning_count: int  # 解決していない(resolved_at が空の)警告の件数


@router.get("/lines/{line_code}/plans", response_model=list[PlanOut])
def list_line_plans(
    line_code: str,
    date: dt.date | None = Query(default=None, description="YYYY-MM-DD。省略すると今日"),
    session: Session = Depends(get_session),
) -> list[Plan]:
    """その日に計画開始〜終了が重なる有効な計画を、計画開始の順で返す。"""
    day = date or clock.now().date()
    day_start = dt.datetime.combine(day, dt.time(), tzinfo=clock.JST)
    day_end = day_start + dt.timedelta(days=1)
    stmt = (
        select(Plan)
        .where(
            Plan.line_code == line_code,
            Plan.status == PLAN_ACTIVE,
            Plan.planned_start.is_not(None),
            Plan.planned_end.is_not(None),
            Plan.planned_start < day_end,
            Plan.planned_end > day_start,
        )
        .order_by(Plan.planned_start, Plan.kitting_no, Plan.lot_no)
    )
    return list(session.scalars(stmt))


@router.get("/sync/status", response_model=SyncStatusOut)
def sync_status(session: Session = Depends(get_session)) -> SyncStatusOut:
    """直近の計画の同期の結果と、解決していない警告の件数。"""
    run = session.scalars(select(PlanSyncRun).order_by(PlanSyncRun.id.desc()).limit(1)).first()
    count = session.scalar(
        select(func.count()).select_from(PlanSyncWarning).where(PlanSyncWarning.resolved_at.is_(None))
    )
    return SyncStatusOut(
        last_run=SyncRunOut.model_validate(run) if run is not None else None,
        warning_count=count or 0,
    )
