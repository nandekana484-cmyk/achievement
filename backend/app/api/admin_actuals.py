"""管理画面の「実績の書き出し」のAPI(既存アプリに戻すための CSV)。管理者のログインが要る。詳細: docs/design/actuals-export.md"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.core.config import get_config
from app.db.models import Operator
from app.db.session import get_session
from app.services import actuals_export
from app.services.actuals_export import ExportIn, ExportOut
from app.services.actuals_rows import ActualsListOut, build_rows
from app.services.errors import RuleViolation
from app.services.masters import get_line

router = APIRouter(prefix="/api/admin/actuals", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


def _check_period(date_from: dt.date, date_to: dt.date) -> None:
    max_days = get_config().reports.max_days
    if date_to < date_from:
        raise RuleViolation("期間の終わりは、始め以降の日付にしてください")
    if (date_to - date_from).days + 1 > max_days:
        raise RuleViolation(f"期間は {max_days} 日までにしてください")


def _line(session: Session, line_code: str | None) -> str | None:
    return get_line(session, line_code).line_code if line_code else None


@router.get("", response_model=ActualsListOut)
def list_actuals(
    _: Admin, session: Db,
    date_from: dt.date = Query(alias="from", description="完了日(稼働日)の始め(YYYY-MM-DD)"),
    date_to: dt.date = Query(alias="to", description="完了日(稼働日)の終わり(YYYY-MM-DD。含む)"),
    line_code: str | None = Query(default=None, description="省略するとすべてのライン"),
) -> ActualsListOut:
    """書き出しの一覧(片付けが終わった計画。1行 = キッティングNo.+ロットNo.)。"""
    _check_period(date_from, date_to)
    return build_rows(session, date_from, date_to, _line(session, line_code), get_config().schedule.day_start)


@router.post("/export", response_model=ExportOut)
def export(admin: Admin, session: Db, body: ExportIn) -> ExportOut:
    """直した数を確かめて CSV を書き出し、履歴を残す。ロットの合計が累計と合わなければ 409。"""
    _check_period(body.date_from, body.date_to)
    body = body.model_copy(update={"line_code": _line(session, body.line_code)})
    cfg = get_config()
    return actuals_export.export_actuals(session, admin, body, cfg.paths.exchange_dir, cfg.schedule.day_start)


@router.get("/exports", response_model=list[ExportOut])
def exports(_: Admin, session: Db) -> list[ExportOut]:
    """書き出しの履歴(新しい順に50件)。"""
    return actuals_export.list_exports(session)


@router.get(
    "/exports/{export_id}/file",
    response_class=Response,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}}}},
)
def export_file(_: Admin, session: Db, export_id: int) -> Response:
    """書き出した CSV のダウンロード(保存したものと同じ中身)。"""
    name, content = actuals_export.export_file(session, export_id)
    return Response(content=content, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
