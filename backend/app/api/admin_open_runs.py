"""管理画面の「終了していない古い記録」のAPI。管理者のログインが要る。ルールは services/admin_open_runs.py。"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.core.config import get_config
from app.db.models import Operator
from app.db.session import get_session
from app.services import admin_open_runs
from app.services.admin_open_runs import OpenRunOut, OpenRunResultOut

router = APIRouter(prefix="/api/admin/open-runs", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


class EndIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    end_at: dt.datetime = Field(description="終了の時刻(開始より後、今より前)")
    produced_qty: int | None = Field(default=None, description="生産の区切りのときの良品数")
    reason: str = Field(max_length=20, description="訂正の理由(mistake・forgot・wrong_qty・other)")
    note: str | None = Field(default=None, max_length=500)


class VoidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=500)


def _cfg() -> tuple[dt.time, int]:
    s = get_config().schedule
    return s.day_start, s.display_extend_max_hours


@router.get("", response_model=list[OpenRunOut])
def list_open_runs(_: Admin, session: Db, line_code: str | None = Query(default=None, max_length=20)) -> list[OpenRunOut]:
    """終了していない古い記録(表示範囲を広げても現場の画面に入らないもの)。ラインで絞り込める。"""
    return admin_open_runs.list_open_runs(session, *_cfg(), line_code)


@router.post("/{event_id}/end", response_model=OpenRunResultOut)
def end_open_run(event_id: int, admin: Admin, session: Db, body: EndIn) -> OpenRunResultOut:
    """終了の時刻を入れる。片付けなら、計画が完了になる。"""
    return admin_open_runs.end_open_run(session, admin, event_id, body.end_at, body.produced_qty, body.reason, body.note, *_cfg())


@router.post("/{event_id}/void", response_model=OpenRunResultOut)
def void_open_run(event_id: int, admin: Admin, session: Db, body: VoidIn) -> OpenRunResultOut:
    """取り消す(取り消しの印。物理削除しない)。"""
    return admin_open_runs.void_open_run(session, admin, event_id, body.reason, body.note, *_cfg())
