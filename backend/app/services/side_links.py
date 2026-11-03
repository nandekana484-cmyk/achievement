"""面1と面2の紐づけの読み方(実績の書き出し。開発指針 5.9)と、管理画面の「ひも付けの確認」。詳細: docs/design/actuals-export.md

- 明示の紐づけ(現場の作業者か管理者が保存したもの。services/side_link_store.py)は、キー H より優先する
- キー H: 同じロットNo.で、キッティングNo.から回を除いた部分(ファイルNo.-ライン-発行年月日-発行順)が同じもの
- 明示の紐づけも H もない面1は、同じ (ロットNo., ファイルNo.) に面2の計画があれば「ひも付けの確認」に出し、管理者が確定する
- 1つの面1は1つの面2とだけ、1つの面2は1つの面1とだけつながる
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Operator, Plan
from app.db.session import write_transaction
from app.domain.kitting_no import without_run
from app.services import audit
from app.services.completions import latest_completion
from app.services.errors import NotFound, RuleViolation
from app.services.side_link_export import last_export_at
from app.services.side_link_store import (
    ACTION_LINK,
    ACTION_SKIP,
    SOURCE_ADMIN,
    Links,
    add_row,
    current_links,
    who,
)

State = Literal["alone", "h", "confirmed", "unlinked", "pending"]


@dataclass(frozen=True)
class Side1Link:
    """面1の計画のロットの、面2とのひも付けの状態。"""

    state: State  # alone=面2の計画が無い / h=キーHでつながる / confirmed=明示の紐づけ / unlinked=つながないと確定 / pending=未確定
    side2_kitting_no: str | None = None


class LinkCandidateOut(BaseModel):
    kitting_no: str  # 面2の計画
    issue_date: dt.date
    paired_with: str | None  # すでにつながっている面1の計画(選べない)


class LinkCheckOut(BaseModel):
    """ひも付けの確認の1行(面1の計画のロットごと)。"""

    lot_no: str
    file_no: str
    side1_kitting_no: str
    side1_issue_date: dt.date
    side1_completed: bool
    state: Literal["pending", "confirmed", "unlinked"]
    side2_kitting_no: str | None  # 確定した面2(つながないなら空)
    decided_by: str | None
    decided_source: str | None  # field(現場の作業者)/ admin(管理者)
    decided_at: dt.datetime | None
    suggested: str | None  # 初期の選択(発行日が最も近い、まだつながっていない面2)
    candidates: list[LinkCandidateOut]


def _plans(session: Session, lot_no: str, file_no: str, side: int) -> list[Plan]:
    return list(session.scalars(select(Plan).where(
        Plan.lot_no == lot_no, Plan.file_no == file_no, Plan.run_no == side, Plan.status == PLAN_ACTIVE,
    ).order_by(Plan.kitting_no)))


def _active(session: Session, kitting_no: str | None) -> bool:
    return kitting_no is not None and session.scalars(
        select(Plan.lot_no).where(Plan.kitting_no == kitting_no, Plan.status == PLAN_ACTIVE)).first() is not None


def _taken(links: Links, side2_kno: str, side1_kno: str) -> bool:
    """面2が、ほかの面1と明示で紐づいている(キー H の自動のつなぎには使えない)。"""
    rec = links.by_side2.get(side2_kno)
    return rec is not None and rec.side1 != side1_kno


def link_for_side1(session: Session, lot_no: str, file_no: str, side1_kno: str, links: Links | None = None) -> Side1Link:
    """面1の計画のロットの状態。明示の紐づけ(管理者・現場)は、キー H より優先する。"""
    links = links or current_links(session)
    side2 = [p.kitting_no for p in _plans(session, lot_no, file_no, 2)]
    if not side2:
        return Side1Link("alone")
    rec = links.by_side1.get(side1_kno)
    if rec is not None and rec.side2 in side2:
        return Side1Link("confirmed", rec.side2)
    if rec is not None and _active(session, rec.side2):
        return Side1Link("alone")  # 紐づけた面2に、このロットが無い(対応するロットが無いので、面1の行を単独で出す)
    if side1_kno in links.skip:
        return Side1Link("unlinked")
    h = without_run(side1_kno)
    match = next((k for k in side2 if without_run(k) == h and not _taken(links, k, side1_kno)), None)
    return Side1Link("h", match) if match else Side1Link("pending")  # 未確定(紐づけた面2が取り消された場合も)


def side1_for_side2(session: Session, lot_no: str, file_no: str, side2_kno: str, links: Links | None = None) -> str | None:
    """面2の計画のロットにつながる面1の計画(明示の紐づけ、無ければキー H)。無ければ None。"""
    links = links or current_links(session)
    side1 = [p.kitting_no for p in _plans(session, lot_no, file_no, 1)]
    rec = links.by_side2.get(side2_kno)
    if rec is not None and rec.side1 in side1:
        return rec.side1
    if rec is not None and _active(session, rec.side1):
        return None  # 紐づけた面1に、このロットが無い
    h = without_run(side2_kno)
    return next((k for k in side1 if without_run(k) == h and k not in links.by_side1), None)


def link_checks(session: Session, lots: set[tuple[str, str]]) -> list[LinkCheckOut]:
    """(ロットNo., ファイルNo.) ごとに、H でつながらない面1の計画(未確定と、確定したもの)。"""
    links = current_links(session)
    out: list[LinkCheckOut] = []
    for lot_no, file_no in sorted(lots):
        side2 = _plans(session, lot_no, file_no, 2)
        if not side2:
            continue
        for p in _plans(session, lot_no, file_no, 1):
            link = link_for_side1(session, lot_no, file_no, p.kitting_no, links)
            if link.state in ("pending", "confirmed", "unlinked"):
                out.append(_check(session, p, link, side2, links))
    return out


def _check(session: Session, side1: Plan, link: Side1Link, side2: list[Plan], links: Links) -> LinkCheckOut:
    candidates = [
        LinkCandidateOut(kitting_no=c.kitting_no, issue_date=c.issue_date, paired_with=_partner_other_than(session, side1, c.kitting_no, links))
        for c in side2
    ]
    free = [c for c in candidates if c.paired_with is None]
    suggested = min(free, key=lambda c: (abs((c.issue_date - side1.issue_date).days), c.kitting_no)).kitting_no if free else None
    rec = links.by_side1.get(side1.kitting_no) if link.state == "confirmed" else links.skip.get(side1.kitting_no)
    return LinkCheckOut(
        lot_no=side1.lot_no, file_no=side1.file_no, side1_kitting_no=side1.kitting_no, side1_issue_date=side1.issue_date,
        side1_completed=latest_completion(session, side1.kitting_no) is not None, state=link.state,
        side2_kitting_no=link.side2_kitting_no, decided_by=who(session, rec.decided_by) if rec else None,
        decided_source=rec.source if rec else None, decided_at=rec.decided_at if rec else None, suggested=suggested,
        candidates=candidates,
    )


def _partner_other_than(session: Session, side1: Plan, side2_kno: str, links: Links) -> str | None:
    partner = side1_for_side2(session, side1.lot_no, side1.file_no, side2_kno, links)
    return partner if partner != side1.kitting_no else None


def partner_of_side2(session: Session, side2_kno: str, links: Links | None = None) -> str | None:
    """面2の計画の、今の面1の相手(明示の紐づけ、無ければキー H。ロットのどれかでつながっていれば)。"""
    links = links or current_links(session)
    for p in session.scalars(select(Plan).where(Plan.kitting_no == side2_kno, Plan.status == PLAN_ACTIVE).order_by(Plan.lot_no)):
        partner = side1_for_side2(session, p.lot_no, p.file_no, side2_kno, links)
        if partner:
            return partner
    rec = links.by_side2.get(side2_kno)
    return rec.side1 if rec else None


def confirm(session: Session, admin: Operator, lot_no: str, side1_kno: str, side2_kno: str | None) -> LinkCheckOut:
    """面1の計画のロットを、面2の計画に確定する(side2_kno が空なら「つながない」)。やり直しは新しい行で上書きする。"""
    side1 = session.get(Plan, (side1_kno, lot_no))
    if side1 is None or side1.status != PLAN_ACTIVE or side1.run_no != 1:
        raise NotFound(f"面1の計画(キッティングNo. {side1_kno}、ロットNo. {lot_no})が見つかりません")
    links = current_links(session)
    link = link_for_side1(session, lot_no, side1.file_no, side1_kno, links)
    if link.state == "alone":
        raise RuleViolation("同じロットNo.・ファイルNo.の面2の計画がありません(面1の行をそのまま書き出します)")
    if link.state == "h":
        raise RuleViolation(f"キッティングNo.で面2の計画({link.side2_kitting_no})とつながっているため、確定は要りません")
    if side2_kno is not None:
        side2 = session.get(Plan, (side2_kno, lot_no))
        if side2 is None or side2.status != PLAN_ACTIVE or side2.run_no != 2 or side2.file_no != side1.file_no:
            raise RuleViolation(f"面2の計画 {side2_kno} は、同じロットNo.・ファイルNo.の有効な面2の計画ではありません")
        partner = _partner_other_than(session, side1, side2_kno, links)
        if partner:
            raise RuleViolation(f"面2の計画 {side2_kno} は、すでに面1の計画 {partner} とつながっています")
    previous = link.side2_kitting_no
    with write_transaction(session):
        row = add_row(session, action=ACTION_LINK if side2_kno else ACTION_SKIP, side1=side1_kno, side2=side2_kno, source=SOURCE_ADMIN,
                      actor_id=admin.id, lot_no=lot_no, previous_partner=previous,
                      exported_at=last_export_at(session, {k for k in (side1_kno, side2_kno, previous) if k}))
        audit.record_change(session, admin.id, "side_links", side1_kno, "link" if side2_kno else "skip",
                            {"side2": previous}, {"side2": side2_kno, "lot_no": lot_no, "id": row.id})
        session.commit()
    links = current_links(session)
    return _check(session, side1, link_for_side1(session, lot_no, side1.file_no, side1_kno, links),
                  _plans(session, lot_no, side1.file_no, 2), links)
