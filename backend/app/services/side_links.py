"""面1と面2の計画のひも付け(実績の書き出し。開発指針 5.9)。詳細: docs/design/actuals-export.md

- キー H: 同じロットNo.で、キッティングNo.から回を除いた部分(ファイルNo.-ライン-発行年月日-発行順)が同じもの
- H でつながらない面1は、同じ (ロットNo., ファイルNo.) に面2の計画があれば「ひも付けの確認」に出し、管理者が確定する
- 確定は side_links に残す(やり直しは新しい行。同じ面1の最新の行を使う)。1つの面2の計画につながる面1は1つだけ
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_ACTIVE, Operator, Plan, SideLink
from app.db.session import write_transaction
from app.domain.kitting_no import without_run
from app.services.completions import latest_completion
from app.services.errors import NotFound, RuleViolation

State = Literal["alone", "h", "confirmed", "unlinked", "pending"]


@dataclass(frozen=True)
class Side1Link:
    """面1の計画のロットの、面2とのひも付けの状態。"""

    state: State  # alone=面2の計画が無い / h=キーHでつながる / confirmed=確定した / unlinked=つながないと確定 / pending=未確定
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
    decided_at: dt.datetime | None
    suggested: str | None  # 初期の選択(発行日が最も近い、まだつながっていない面2)
    candidates: list[LinkCandidateOut]


def _plans(session: Session, lot_no: str, file_no: str, side: int) -> list[Plan]:
    return list(session.scalars(select(Plan).where(
        Plan.lot_no == lot_no, Plan.file_no == file_no, Plan.run_no == side, Plan.status == PLAN_ACTIVE,
    ).order_by(Plan.kitting_no)))


def latest_decision(session: Session, side1_kno: str, lot_no: str) -> SideLink | None:
    return session.scalars(select(SideLink).where(SideLink.side1_kitting_no == side1_kno, SideLink.lot_no == lot_no)
                           .order_by(SideLink.id.desc())).first()


def link_for_side1(session: Session, lot_no: str, file_no: str, side1_kno: str) -> Side1Link:
    side2 = [p.kitting_no for p in _plans(session, lot_no, file_no, 2)]
    if not side2:
        return Side1Link("alone")
    h = without_run(side1_kno)
    match = next((k for k in side2 if without_run(k) == h), None)
    if match:
        return Side1Link("h", match)
    decision = latest_decision(session, side1_kno, lot_no)
    if decision is not None and decision.side2_kitting_no is None:
        return Side1Link("unlinked")
    if decision is not None and decision.side2_kitting_no in side2:
        return Side1Link("confirmed", decision.side2_kitting_no)
    return Side1Link("pending")  # 未確定(確定した面2の計画が取り消された場合も)


def side1_for_side2(session: Session, lot_no: str, file_no: str, side2_kno: str) -> str | None:
    """面2の計画のロットにつながる面1の計画(キーHか、確定したもの)。無ければ None。"""
    side1 = [p.kitting_no for p in _plans(session, lot_no, file_no, 1)]
    h = without_run(side2_kno)
    match = next((k for k in side1 if without_run(k) == h), None)
    if match:
        return match
    return next((k for k in side1 if link_for_side1(session, lot_no, file_no, k).side2_kitting_no == side2_kno), None)


def link_checks(session: Session, lots: set[tuple[str, str]]) -> list[LinkCheckOut]:
    """(ロットNo., ファイルNo.) ごとに、H でつながらない面1の計画(未確定と、確定したもの)。"""
    out: list[LinkCheckOut] = []
    for lot_no, file_no in sorted(lots):
        side2 = _plans(session, lot_no, file_no, 2)
        if not side2:
            continue
        for p in _plans(session, lot_no, file_no, 1):
            link = link_for_side1(session, lot_no, file_no, p.kitting_no)
            if link.state in ("pending", "confirmed", "unlinked"):
                out.append(_check(session, p, link, side2))
    return out


def _check(session: Session, side1: Plan, link: Side1Link, side2: list[Plan]) -> LinkCheckOut:
    candidates = [
        LinkCandidateOut(kitting_no=c.kitting_no, issue_date=c.issue_date,
                         paired_with=_partner_other_than(session, side1, c.kitting_no))
        for c in side2
    ]
    free = [c for c in candidates if c.paired_with is None]
    suggested = min(free, key=lambda c: (abs((c.issue_date - side1.issue_date).days), c.kitting_no)).kitting_no if free else None
    decision = latest_decision(session, side1.kitting_no, side1.lot_no) if link.state != "pending" else None
    return LinkCheckOut(
        lot_no=side1.lot_no, file_no=side1.file_no, side1_kitting_no=side1.kitting_no, side1_issue_date=side1.issue_date,
        side1_completed=latest_completion(session, side1.kitting_no) is not None, state=link.state,
        side2_kitting_no=link.side2_kitting_no, decided_by=_who(session, decision.decided_by) if decision else None,
        decided_at=decision.decided_at if decision else None, suggested=suggested, candidates=candidates,
    )


def _partner_other_than(session: Session, side1: Plan, side2_kno: str) -> str | None:
    partner = side1_for_side2(session, side1.lot_no, side1.file_no, side2_kno)
    return partner if partner != side1.kitting_no else None


def _who(session: Session, operator_id: int) -> str:
    op = session.get(Operator, operator_id)
    return f"{op.name}({op.worker_id})" if op and op.worker_id else (op.name if op else "")


def confirm(session: Session, admin: Operator, lot_no: str, side1_kno: str, side2_kno: str | None) -> LinkCheckOut:
    """面1の計画のロットを、面2の計画に確定する(side2_kno が空なら「つながない」)。やり直しは新しい行で上書きする。"""
    side1 = session.get(Plan, (side1_kno, lot_no))
    if side1 is None or side1.status != PLAN_ACTIVE or side1.run_no != 1:
        raise NotFound(f"面1の計画(キッティングNo. {side1_kno}、ロットNo. {lot_no})が見つかりません")
    link = link_for_side1(session, lot_no, side1.file_no, side1_kno)
    if link.state == "alone":
        raise RuleViolation("同じロットNo.・ファイルNo.の面2の計画がありません(面1の行をそのまま書き出します)")
    if link.state == "h":
        raise RuleViolation(f"キッティングNo.で面2の計画({link.side2_kitting_no})とつながっているため、確定は要りません")
    if side2_kno is not None:
        side2 = session.get(Plan, (side2_kno, lot_no))
        if side2 is None or side2.status != PLAN_ACTIVE or side2.run_no != 2 or side2.file_no != side1.file_no:
            raise RuleViolation(f"面2の計画 {side2_kno} は、同じロットNo.・ファイルNo.の有効な面2の計画ではありません")
        partner = _partner_other_than(session, side1, side2_kno)
        if partner:
            raise RuleViolation(f"面2の計画 {side2_kno} は、すでに面1の計画 {partner} とつながっています")
    with write_transaction(session):
        session.add(SideLink(lot_no=lot_no, side1_kitting_no=side1_kno, side2_kitting_no=side2_kno,
                             decided_by=admin.id, decided_at=clock.now()))
        session.commit()
    side2_plans = _plans(session, lot_no, side1.file_no, 2)
    return _check(session, side1, link_for_side1(session, lot_no, side1.file_no, side1_kno), side2_plans)
