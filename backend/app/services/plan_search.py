"""計画の検索(開発指針 7.1)。キッティングNo.・ロットNo.・基板名の一部で探し、当たったキッティングNo.のまとまりを返す。

英字の大文字・小文字と全角・半角の違いを無視するため、NFKC と casefold をかけて Python で比べる
(SQLite の LIKE ではできないため。有効な計画は数千件程度なので、全件を読んでも短く終わる)。
"""

from __future__ import annotations

import unicodedata
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Plan
from app.domain.normalize import normalize_mounting_line
from app.services.kitting_plans import KittingGroup, load_active_groups
from app.services.plan_views import SearchHitOut, kitting_plan_out

MAX_RESULTS = 20


def fold(text: str | None) -> str:
    """比べるための形(全角→半角、大文字・小文字の違いをなくす)。"""
    return unicodedata.normalize("NFKC", text or "").casefold().strip()


def _matches(plan: Plan, needle: str) -> list[str]:
    found = []
    if needle in fold(plan.kitting_no):
        found.append("キッティングNo.")
    if needle in fold(plan.lot_no):
        found.append(f"ロットNo. {plan.lot_no}")
    if needle in fold(plan.product_name):
        found.append(f"基板名 {plan.product_name}")
    return found


def search_plans(session: Session, q: str, now: datetime, line_code: str | None = None) -> list[SearchHitOut]:
    """一部が一致する有効なまとまりを、計画開始が今に近い順に最大20件。日程が空のものは最後。"""
    needle = fold(q)
    if not needle:
        return []
    stmt = select(Plan).where(Plan.status == PLAN_ACTIVE)
    if line_code:
        stmt = stmt.where(Plan.line_code == normalize_mounting_line(line_code))
    matched: dict[str, list[str]] = {}
    for p in session.scalars(stmt):
        for m in _matches(p, needle):
            items = matched.setdefault(p.kitting_no, [])
            if m not in items:
                items.append(m)

    def distance(g: KittingGroup) -> tuple:
        if g.planned_start is None:
            return (1, 0.0, g.kitting_no)
        return (0, abs((g.planned_start - now).total_seconds()), g.kitting_no)

    groups = sorted(load_active_groups(session, matched), key=distance)[:MAX_RESULTS]
    return [SearchHitOut(plan=kitting_plan_out(g), matched=matched[g.kitting_no]) for g in groups]
