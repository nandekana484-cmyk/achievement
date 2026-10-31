"""丁取りが引けない計画の一覧(管理画面。見るだけ)。有効な計画を、キッティングNo.のまとまりで見る。

詳細: docs/design/metrics.md
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Plan
from app.integration.legacy.teitori import STATUS_OK
from app.services.kitting_plans import group_lots
from app.services.teitori_lookup import lookup_teitori

LIMIT = 500


class UnresolvedPlanOut(BaseModel):
    kitting_no: str
    file_no: str
    line_code: str
    status: str  # 既存アプリの status、または no_row(丁取りの行が無い)


class UnresolvedOut(BaseModel):
    total_plans: int  # 有効な計画(キッティングNo.)の数
    unresolved: int  # 丁取りが引けない計画の数
    by_status: dict[str, int]
    plans: list[UnresolvedPlanOut]  # 計画開始の新しい順。LIMIT 件まで
    truncated: bool


def unresolved_plans(session: Session) -> UnresolvedOut:
    groups = group_lots(session.scalars(select(Plan).where(Plan.status == PLAN_ACTIVE)))
    groups.sort(key=lambda g: (g.planned_start is not None, g.planned_start), reverse=True)
    found: list[UnresolvedPlanOut] = []
    for g in groups:
        teitori, status = lookup_teitori(session, g.first.file_no, g.first.line_code)
        if status != STATUS_OK or teitori is None:
            found.append(UnresolvedPlanOut(kitting_no=g.kitting_no, file_no=g.file_no, line_code=g.line_code, status=status))
    return UnresolvedOut(
        total_plans=len(groups), unresolved=len(found), by_status=dict(Counter(p.status for p in found)),
        plans=found[:LIMIT], truncated=len(found) > LIMIT,
    )
