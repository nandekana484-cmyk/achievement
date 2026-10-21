"""計画の検索(開発指針 7.1)。キッティングNo.・ロットNo.・品名の一部で、有効な計画を探す。

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

MAX_RESULTS = 20


def fold(text: str | None) -> str:
    """比べるための形(全角→半角、大文字・小文字の違いをなくす)。"""
    return unicodedata.normalize("NFKC", text or "").casefold().strip()


def search_plans(session: Session, q: str, now: datetime, line_code: str | None = None) -> list[Plan]:
    """一部が一致する有効な計画を、計画開始が今に近い順に最大20件。日程が空の計画は最後。"""
    needle = fold(q)
    if not needle:
        return []
    stmt = select(Plan).where(Plan.status == PLAN_ACTIVE)
    if line_code:
        stmt = stmt.where(Plan.line_code == normalize_mounting_line(line_code))
    hits = [
        p for p in session.scalars(stmt)
        if needle in fold(p.kitting_no) or needle in fold(p.lot_no) or needle in fold(p.product_name)
    ]

    def distance(p: Plan) -> tuple:
        if p.planned_start is None:
            return (1, 0.0, p.kitting_no)
        return (0, abs((p.planned_start - now).total_seconds()), p.kitting_no)

    return sorted(hits, key=distance)[:MAX_RESULTS]
