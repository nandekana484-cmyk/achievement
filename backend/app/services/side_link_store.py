"""面1と面2の紐づけの履歴(side_links)を読んで「今有効な紐づけ」にまとめる、1か所の読み方。管理者も現場の作業者も同じ表・同じ規則。

履歴を作った順に読み、後の行が前の行を上書きする(最後に保存したものが有効)。
- link: 面2の相手を面1にする。同じ面2・同じ面1の古い紐づけは外れる(1つの面1は1つの面2とだけ、1つの面2は1つの面1とだけ)
- unlink: 面2の紐づけを外す(キー H の自動のつなぎには戻る)
- skip: 管理者の「つながない」(面1は書き出さない。キー H でもつなげない)
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import Operator, SideLink

ACTION_LINK = "link"
ACTION_UNLINK = "unlink"
ACTION_SKIP = "skip"
SOURCE_FIELD = "field"
SOURCE_ADMIN = "admin"


@dataclass(frozen=True)
class LinkRec:
    id: int
    side1: str
    side2: str | None
    source: str
    decided_by: int
    decided_at: dt.datetime


@dataclass
class Links:
    """今有効な紐づけ。"""

    by_side2: dict[str, LinkRec] = field(default_factory=dict)
    by_side1: dict[str, LinkRec] = field(default_factory=dict)
    skip: dict[str, LinkRec] = field(default_factory=dict)  # 管理者の「つながない」の面1

    def _drop_side2(self, side2: str) -> None:
        old = self.by_side2.pop(side2, None)
        if old is not None:
            self.by_side1.pop(old.side1, None)

    def _drop_side1(self, side1: str) -> None:
        old = self.by_side1.pop(side1, None)
        if old is not None and old.side2 is not None:
            self.by_side2.pop(old.side2, None)


def current_links(session: Session) -> Links:
    links = Links()
    for r in session.scalars(select(SideLink).order_by(SideLink.id)):
        rec = LinkRec(r.id, r.side1_kitting_no, r.side2_kitting_no, r.source, r.decided_by, r.decided_at)
        if r.action == ACTION_LINK and rec.side2 is not None:
            links._drop_side2(rec.side2)
            links._drop_side1(rec.side1)
            links.skip.pop(rec.side1, None)
            links.by_side2[rec.side2], links.by_side1[rec.side1] = rec, rec
        elif r.action == ACTION_UNLINK and rec.side2 is not None:
            links._drop_side2(rec.side2)
        elif r.action == ACTION_SKIP:
            links._drop_side1(rec.side1)
            links.skip[rec.side1] = rec
    return links


def add_row(
    session: Session, *, action: str, side1: str, side2: str | None, source: str, actor_id: int, lot_no: str = "",
    previous_partner: str | None = None, exported_at: dt.datetime | None = None,
) -> SideLink:
    row = SideLink(
        lot_no=lot_no, side1_kitting_no=side1, side2_kitting_no=side2, decided_by=actor_id, decided_at=clock.now(),
        action=action, source=source, previous_partner=previous_partner, exported_at=exported_at,
    )
    session.add(row)
    session.flush()
    return row


def who(session: Session, operator_id: int | None) -> str:
    """名前(作業者ID)。"""
    op = session.get(Operator, operator_id) if operator_id is not None else None
    return f"{op.name}({op.worker_id})" if op and op.worker_id else (op.name if op else "")
