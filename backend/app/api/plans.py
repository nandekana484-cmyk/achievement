"""計画と、計画の同期状況のAPI。"""

from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import Plan, PlanSyncRun, PlanSyncWarning
from app.db.session import get_session
from app.services.board import plans_for_day
from app.services.views import PlanOut

router = APIRouter(prefix="/api", tags=["plans"])


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
    # その回に読んだ月次DBの一覧と、DBごとの計画の件数({"read": [...], "skipped": [...]})
    legacy_dbs: dict | None

    @field_validator("legacy_dbs", mode="before")
    @classmethod
    def _parse_legacy_dbs(cls, v):  # noqa: ANN001, ANN206
        return json.loads(v) if isinstance(v, str) else v


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
    return plans_for_day(session, line_code, date or clock.now().date())


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
