"""管理画面の集計のAPI: 区間の CSV と日報。管理者のログインが要る。詳細: docs/design/reports.md"""

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
from app.services import daily_report, report_csv
from app.services.errors import RuleViolation
from app.services.masters import get_line
from app.services.report_intervals import build_intervals

router = APIRouter(prefix="/api/admin/reports", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


@router.get(
    "/intervals.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}}}},
)
def intervals_csv(
    _: Admin, session: Db,
    date_from: dt.date = Query(alias="from", description="稼働日の始め(YYYY-MM-DD)"),
    date_to: dt.date = Query(alias="to", description="稼働日の終わり(YYYY-MM-DD。含む)"),
    line_code: str | None = Query(default=None, description="省略するとすべてのライン"),
) -> Response:
    """区間の CSV(1行 = 1つの区間。BOM 付きの UTF-8、CRLF)。期間の上限は config.toml の [reports] max_days。"""
    cfg = get_config()
    if date_to < date_from:
        raise RuleViolation("期間の終わりは、始め以降の日付にしてください")
    if (date_to - date_from).days + 1 > cfg.reports.max_days:
        raise RuleViolation(f"期間は {cfg.reports.max_days} 日までにしてください")
    code = get_line(session, line_code).line_code if line_code else None
    rows = build_intervals(session, date_from, date_to, code, cfg.schedule.day_start)
    name = report_csv.csv_filename(date_from, date_to, code)
    return Response(
        content=report_csv.intervals_csv(rows), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/daily", response_model=daily_report.DailyReportOut)
def daily(
    _: Admin, session: Db,
    date: dt.date = Query(description="稼働日(YYYY-MM-DD)"),
    line_code: str = Query(description="ライン"),
) -> daily_report.DailyReportOut:
    """日報の表示に要る値(区間、上段・下段の棒、生産数とNG数の合計)。"""
    return daily_report.daily_report(session, line_code, date, get_config().schedule.day_start)
