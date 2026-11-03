"""生産記録票の1枚 = 両面の1組(1回目 = 面1、2回目 = 面2)。組み合わせは実績の書き出しと同じ読み方(AD-19)。

明示の紐づけ(side_link_store.current_links)が先、無ければキー H。印刷のためだけの規則は持たない。
詳細: docs/design/production-record.md
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE
from app.services.errors import NotFound
from app.services.kitting_plans import KittingGroup, load_group
from app.services.side_link_store import Links, current_links
from app.services.side_links import link_for_side1, partner_of_side2


@dataclass
class RecordPair:
    side1: KittingGroup | None  # 1回目
    side2: KittingGroup | None  # 2回目

    @property
    def key(self) -> str:
        """この組を開くときのキッティングNo.(2回目があれば2回目)。"""
        return (self.side2 or self.side1).kitting_no  # type: ignore[union-attr]

    @property
    def unlinked_side2(self) -> bool:
        """面1とつながっていない面2。"""
        return self.side1 is None and self.side2 is not None

    def faces(self) -> list[KittingGroup]:
        return [g for g in (self.side1, self.side2) if g is not None]


def partner_of_side1(session: Session, group: KittingGroup, links: Links) -> str | None:
    """面1の計画の、今の面2の相手(明示の紐づけ、無ければキー H)。"""
    rec = links.by_side1.get(group.kitting_no)
    if rec is not None and rec.side2 is not None:
        return rec.side2
    for lot in group.lots:
        link = link_for_side1(session, lot.lot_no, lot.file_no, group.kitting_no, links)
        if link.state in ("h", "confirmed") and link.side2_kitting_no:
            return link.side2_kitting_no
    return None


def _active_group(session: Session, kitting_no: str | None) -> KittingGroup | None:
    if kitting_no is None:
        return None
    try:
        group = load_group(session, kitting_no)
    except NotFound:
        return None
    return group if group.status == PLAN_ACTIVE else None


def pair_of(session: Session, group: KittingGroup, links: Links | None = None) -> RecordPair:
    """有効な計画のまとまりが入る組。相手が取り消されていれば、つながっていない扱い。"""
    links = links or current_links(session)
    if group.run_no == 2:
        return RecordPair(_active_group(session, partner_of_side2(session, group.kitting_no, links)), group)
    return RecordPair(group, _active_group(session, partner_of_side1(session, group, links)))
