"""計画と、計画の同期状況のAPI。"""

from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_config
from app.db.models import PlanSyncRun, PlanSyncWarning
from app.db.session import get_session
from app.domain.workday import workday_of, workday_range
from app.services import plan_search
from app.services.kitting_plans import load_active_groups
from app.services.plan_query import kitting_nos_overlapping
from app.services.plan_views import KittingPlanOut, SearchHitOut, kitting_plan_out

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


@router.get("/lines/{line_code}/plans", response_model=list[KittingPlanOut])
def list_line_plans(
    line_code: str,
    date: dt.date | None = Query(default=None, description="稼働日(YYYY-MM-DD)。省略すると今の稼働日"),
    session: Session = Depends(get_session),
) -> list[KittingPlanOut]:
    """稼働日(day_start〜翌日の day_start)に重なる計画のまとまり(キッティングNo.ごと)を、計画開始の順で返す。"""
    day_start = get_config().schedule.day_start
    start, end = workday_range(date or workday_of(clock.now(), day_start), day_start)
    groups = load_active_groups(session, kitting_nos_overlapping(session, line_code, start, end))
    return [kitting_plan_out(g) for g in groups]


@router.get("/plans/search", response_model=list[SearchHitOut])
def search_plans(
    q: str = Query(max_length=100, description="キッティングNo.・ロットNo.・基板名の一部"),
    line_code: str | None = Query(default=None, description="指定すると、そのラインの計画だけ"),
    session: Session = Depends(get_session),
) -> list[SearchHitOut]:
    """一部一致で探し、当たったキッティングNo.のまとまりを返す(大文字・小文字、全角・半角は無視。最大20件)。"""
    return plan_search.search_plans(session, q, clock.now(), line_code)


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
