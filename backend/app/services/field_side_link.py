"""現場の画面での面1と面2の紐づけ(2回目の作業者が、1回目のキッティングNo.を入れて紐づける)。管理者の「外す」も同じ処理。

紐づけは面2のキッティングNo.と面1のキッティングNo.の組で、ロットはロットNo.が同じもの同士を対応させる。
書き出しは、この紐づけ(明示の紐づけ。キー H より優先)をそのまま使い、管理者の確定は待たない。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import datetime as dt
import unicodedata
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Plan
from app.db.session import write_transaction
from app.services import audit, line_operators, masters
from app.services.errors import NotFound, RuleViolation
from app.services.idempotency import run_idempotent
from app.services.kitting_plans import KittingGroup, load_group
from app.services.side_link_export import last_export_at
from app.services.side_link_store import ACTION_LINK, ACTION_UNLINK, Links, add_row, current_links, who
from app.services.side_links import link_for_side1, partner_of_side2, side1_for_side2
from app.services.views.side_link import SideLinkViewOut

_DASHES = str.maketrans({c: "-" for c in "‐‑‒–—―−ー"})


def normalize_kitting_input(text: str) -> str:
    """入力のキッティングNo.: 全角の数字・英字・ハイフンを半角にし、前後の空白を除く。"""
    return unicodedata.normalize("NFKC", text).translate(_DASHES).strip()


class SideLinkCheckOut(BaseModel):
    side1_kitting_no: str  # 入力を整えて探した、面1のキッティングNo.
    errors: list[str]  # 断る理由(1つでもあれば紐づけられない)
    mismatched_lots: list[str]  # 合わないロット(警告。確認すれば紐づけられる)
    exported: bool  # 書き出し済み(変えたら、既存アプリの値を管理者が直す必要がある)
    exported_at: dt.datetime | None
    current_partner: str | None  # 今の相手(直すとき)


def _rows(session: Session, kitting_no: str) -> list[Plan]:
    return list(session.scalars(select(Plan).where(Plan.kitting_no == kitting_no).order_by(Plan.lot_no)))


def _active_rows(session: Session, kitting_no: str) -> list[Plan]:
    return [p for p in _rows(session, kitting_no) if p.status == PLAN_ACTIVE]


def _resolve(session: Session, text: str) -> str:
    """入力に当たるキッティングNo.(そのまま、無ければ英字の大文字・小文字の違いを除いて1つに決まるもの)。"""
    norm = normalize_kitting_input(text)
    if not norm or session.scalars(select(Plan.kitting_no).where(Plan.kitting_no == norm)).first():
        return norm
    same = list(session.scalars(select(Plan.kitting_no).where(func.upper(Plan.kitting_no) == norm.upper()).distinct()))
    return same[0] if len(same) == 1 else norm


def candidates_for(session: Session, side2: list[Plan], links: Links) -> list[str]:
    """面2の計画に紐づけられる面1の候補: 同じロットNo.・ファイルNo.の有効な面1の計画(ほかの面2と明示で紐づいたものは除く)。"""
    lots = {p.lot_no for p in side2}
    found = session.scalars(select(Plan.kitting_no).where(
        Plan.status == PLAN_ACTIVE, Plan.run_no == 1, Plan.file_no == side2[0].file_no, Plan.lot_no.in_(lots)).distinct().order_by(Plan.kitting_no))
    def free(k: str) -> bool:
        rec = links.by_side1.get(k)
        return rec is None or rec.side2 == side2[0].kitting_no or not _active_rows(session, rec.side2 or "")
    return [k for k in found if free(k)]


def view(session: Session, group: KittingGroup, links: Links | None = None) -> SideLinkViewOut | None:
    """計画のまとまりの紐づけの状態(面1・面2以外は None)。"""
    links = links or current_links(session)
    if group.run_no == 2:
        return _view_side2(session, group, links)
    return _view_side1(session, group, links)


def _view_side2(session: Session, group: KittingGroup, links: Links) -> SideLinkViewOut:
    kno = group.kitting_no
    side2 = [p for p in _rows(session, kno) if p.status == PLAN_ACTIVE] or list(group.lots)
    candidates = candidates_for(session, side2, links)
    rec = links.by_side2.get(kno)
    if rec is not None and _active_rows(session, rec.side1):
        return SideLinkViewOut(role="side2", partner=rec.side1, partner_source=rec.source, decided_by=who(session, rec.decided_by),
                               decided_at=rec.decided_at, suggested=None, candidates=candidates)
    auto = next((s for p in side2 if (s := side1_for_side2(session, p.lot_no, p.file_no, kno, links))), None)
    suggested = auto or (candidates[0] if len(candidates) == 1 else None)  # 候補の順: 1. キー H、2. ちょうど1つ
    return SideLinkViewOut(role="side2", partner=None, partner_source="h" if auto else None, decided_by=None, decided_at=None,
                           suggested=suggested, candidates=candidates)


def _view_side1(session: Session, group: KittingGroup, links: Links) -> SideLinkViewOut:
    for lot in group.lots:
        link = link_for_side1(session, lot.lot_no, lot.file_no, group.kitting_no, links)
        if link.state in ("h", "confirmed") and link.side2_kitting_no:
            rec = links.by_side1.get(group.kitting_no) if link.state == "confirmed" else None
            return SideLinkViewOut(role="side1", partner=link.side2_kitting_no, partner_source=rec.source if rec else "h",
                                   decided_by=who(session, rec.decided_by) if rec else None, decided_at=rec.decided_at if rec else None,
                                   suggested=None, candidates=[])
    return SideLinkViewOut(role="side1", partner=None, partner_source=None, decided_by=None, decided_at=None, suggested=None, candidates=[])


def check(session: Session, side2_kno: str, text: str) -> SideLinkCheckOut:
    """紐づける前の確かめ: 断る理由、合わないロットの警告、書き出し済みか。"""
    side2 = _active_rows(session, side2_kno)
    if not side2:
        raise NotFound(f"計画(キッティングNo. {side2_kno})が見つかりません、または取り消されています")
    links = current_links(session)
    side1_kno = _resolve(session, text)
    errors = _errors(session, side2, side1_kno, links)
    mismatched = [] if errors else _mismatched_lots(side2, _active_rows(session, side1_kno))
    current = partner_of_side2(session, side2_kno, links)
    last = last_export_at(session, {k for k in (side2_kno, side1_kno, current) if k})
    return SideLinkCheckOut(side1_kitting_no=side1_kno, errors=errors, mismatched_lots=mismatched, exported=last is not None,
                            exported_at=last, current_partner=current)


def _errors(session: Session, side2: list[Plan], side1_kno: str, links: Links) -> list[str]:
    side2_kno = side2[0].kitting_no
    if side2[0].run_no != 2:
        return ["2回目(面2)の計画だけに、1回目のキッティングNo.を紐づけられます"]
    if not side1_kno:
        return ["1回目のキッティングNo.を入れてください"]
    rows = _rows(session, side1_kno)
    active = [p for p in rows if p.status == PLAN_ACTIVE]
    if not rows:
        return [f"キッティングNo. {side1_kno} の計画が見つかりません"]
    if not active:
        return [f"キッティングNo. {side1_kno} は取り消された計画です(取り消された計画には紐づけられません)"]
    if active[0].run_no != 1:
        return [f"キッティングNo. {side1_kno} は1回目(面1)の計画ではありません"]
    if active[0].file_no != side2[0].file_no:
        return [f"ファイルNo.が違います(2回目 {side2[0].file_no}、1回目 {active[0].file_no})"]
    return _partner_errors(session, side2_kno, side1_kno, active, links)


def _partner_errors(session: Session, side2_kno: str, side1_kno: str, side1: list[Plan], links: Links) -> list[str]:
    """その面1が、ほかの面2と紐づいている(明示でも、キッティングNo.でも)。相手を出して断る。"""
    rec = links.by_side1.get(side1_kno)
    if rec is not None and rec.side2 != side2_kno and _active_rows(session, rec.side2 or ""):
        return [f"{side1_kno} は、すでに {rec.side2} と紐づいています。先に {rec.side2} の紐づけを外してください"]
    for p in side1:
        link = link_for_side1(session, p.lot_no, p.file_no, side1_kno, links)
        if link.state == "h" and link.side2_kitting_no not in (None, side2_kno):
            return [f"{side1_kno} は、キッティングNo.で {link.side2_kitting_no} とつながっています。先に {link.side2_kitting_no} の紐づけを直してください"]
    return []


def _mismatched_lots(side2: list[Plan], side1: list[Plan]) -> list[str]:
    """ロットNo.の組が合わないロット。"""
    a, b = {p.lot_no for p in side2}, {p.lot_no for p in side1}
    return [f"{lot}(2回目だけ)" for lot in sorted(a - b)] + [f"{lot}(1回目だけ)" for lot in sorted(b - a)]


def resolve_actor(session: Session, side2_kno: str, operator_id: int | None, worker_id: str | None) -> int:
    """紐づけた人(作業者ID必須)。指定が無ければ、そのラインの今の担当者(作業者IDで呼び出した人)。"""
    explicit = masters.resolve_operator_ref(session, operator_id, worker_id)
    return line_operators.resolve_recorder(session, load_group(session, side2_kno).line_code, explicit)


class _Applied(BaseModel):
    view: SideLinkViewOut | None


def link(
    session: Session, actor_id: int, source: str, side2_kno: str, text: str, confirm_lot_mismatch: bool, request_id: str,
) -> SideLinkViewOut:
    """面2に面1を紐づける(直しも同じ。最後に保存したものが有効)。断る理由があれば 409。合わないロットは確認してから。"""
    payload = {"side2": side2_kno, "side1": text, "confirm": confirm_lot_mismatch, "actor": actor_id, "source": source}

    def action(now: dt.datetime) -> _Applied:
        chk = check(session, side2_kno, text)
        if chk.errors:
            raise RuleViolation(chk.errors[0])
        if chk.mismatched_lots and not confirm_lot_mismatch:
            raise RuleViolation("ロットNo.の組が合いません: " + "、".join(chk.mismatched_lots) + "。確認してから、もう一度紐づけてください")
        links = current_links(session)
        rec = links.by_side2.get(side2_kno)
        if rec is None or rec.side1 != chk.side1_kitting_no:
            previous = chk.current_partner
            row = add_row(session, action=ACTION_LINK, side1=chk.side1_kitting_no, side2=side2_kno, source=source, actor_id=actor_id,
                          previous_partner=previous, exported_at=chk.exported_at)
            audit.record_change(session, actor_id, "side_links", side2_kno, "link", {"side1": previous},
                                {"side1": chk.side1_kitting_no, "source": source, "id": row.id}, None)
        return _Applied(view=view(session, load_group(session, side2_kno)))

    return run_idempotent(session, request_id, "side_link.link", payload, _Applied, action).view  # type: ignore[return-value]


def unlink(session: Session, actor_id: int, source: str, side2_kno: str, request_id: str | None = None) -> SideLinkViewOut | None:
    """面2の明示の紐づけを外す(キッティングNo.でつながっているものは外せない)。いつでも外せる。"""
    def apply() -> _Applied:
        links = current_links(session)
        rec = links.by_side2.get(side2_kno)
        if rec is None:
            raise RuleViolation("明示の紐づけがありません(キッティングNo.でつながっているものは外せません)")
        row = add_row(session, action=ACTION_UNLINK, side1=rec.side1, side2=side2_kno, source=source, actor_id=actor_id,
                      previous_partner=rec.side1, exported_at=last_export_at(session, {side2_kno, rec.side1}))
        audit.record_change(session, actor_id, "side_links", side2_kno, "unlink", {"side1": rec.side1}, {"side1": None, "source": source, "id": row.id})
        return _Applied(view=view(session, load_group(session, side2_kno)))

    if request_id is not None:
        payload = {"side2": side2_kno, "actor": actor_id, "source": source}
        return run_idempotent(session, request_id, "side_link.unlink", payload, _Applied, lambda _now: apply()).view
    with write_transaction(session):
        result = apply()
        session.commit()
    return result.view

