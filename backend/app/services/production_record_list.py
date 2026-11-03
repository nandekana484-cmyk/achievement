"""生産記録票を印刷する組の一覧(現場の画面)。1組で1行。どちらかの面の完了日が過去31日以内の組。

取り消された計画は出さない。面1とつながっていない面2も1行(「1回目と紐づける」から紐づけの画面へ進む)。
詳細: docs/design/production-record.md
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import RunCompletion
from app.services.completions import latest_completion, valid_completion
from app.services.kitting_plans import KittingGroup, load_active_groups
from app.services.production_record_pair import RecordPair, pair_of
from app.services.side_link_store import current_links

LIST_DAYS = 31


class RecordRowOut(BaseModel):
    kitting_no: str  # 開くときのキッティングNo.(2回目があれば2回目)
    side1_kitting_no: str | None
    side2_kitting_no: str | None
    side1_line: str | None
    side2_line: str | None
    lot_nos: list[str]
    product_name: str
    completed_at: dt.datetime  # どちらかの面の、最新の完了
    side1_completed: bool
    side2_completed: bool
    side2_unlinked: bool  # 面1とつながっていない面2


def _completed_at(session: Session, g: KittingGroup | None) -> dt.datetime | None:
    c = latest_completion(session, g.kitting_no) if g else None
    return c.completed_at if c else None


def _row(session: Session, pair: RecordPair) -> RecordRowOut | None:
    c1, c2 = _completed_at(session, pair.side1), _completed_at(session, pair.side2)
    done = [c for c in (c1, c2) if c is not None]
    if not done:
        return None
    first = pair.side1 or pair.side2
    lots = sorted({lot.lot_no for g in pair.faces() for lot in g.lots})
    return RecordRowOut(
        kitting_no=pair.key, side1_kitting_no=pair.side1.kitting_no if pair.side1 else None,
        side2_kitting_no=pair.side2.kitting_no if pair.side2 else None, side1_line=pair.side1.line_code if pair.side1 else None,
        side2_line=pair.side2.line_code if pair.side2 else None, lot_nos=lots, product_name=first.product_name,  # type: ignore[union-attr]
        completed_at=max(done), side1_completed=c1 is not None, side2_completed=c2 is not None, side2_unlinked=pair.unlinked_side2,
    )


def _matches(row: RecordRowOut, line: str | None, kitting_no: str | None, lot_no: str | None) -> bool:
    if line and line not in (row.side1_line, row.side2_line):
        return False
    if kitting_no and not any(kitting_no.casefold() in (k or "").casefold() for k in (row.side1_kitting_no, row.side2_kitting_no)):
        return False
    return not lot_no or any(lot_no.casefold() in x.casefold() for x in row.lot_nos)


def list_records(session: Session, line: str | None = None, kitting_no: str | None = None, lot_no: str | None = None) -> list[RecordRowOut]:
    """完了日の新しい順。"""
    since = clock.now() - dt.timedelta(days=LIST_DAYS)
    knos = set(session.scalars(select(RunCompletion.kitting_no).where(valid_completion(), RunCompletion.completed_at >= since)))
    links = current_links(session)
    seen: set[str] = set()
    rows: list[RecordRowOut] = []
    for group in load_active_groups(session, knos):
        pair = pair_of(session, group, links)
        if pair.key in seen:
            continue
        seen.add(pair.key)
        row = _row(session, pair)
        if row is not None and (row.completed_at >= since) and _matches(row, line, kitting_no, lot_no):
            rows.append(row)
    return sorted(rows, key=lambda r: (r.completed_at, r.kitting_no), reverse=True)
