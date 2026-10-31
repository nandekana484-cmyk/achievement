"""実績の引き継ぎ(出し直しでキッティングNo.が変わった計画へ、実績を移す)。管理画面の「引き継ぎの確認」。

実績のある計画が取り消された・古い計画になったとき、管理者が移す先を確定する。自動では移さない。
移すときは記録を消さず kitting_no を付け替え、履歴(kitting_handovers)を残し、古い計画に取消の印(理由「引き継ぎ済み」)を付ける。
詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import (
    CANCEL_CARRIED_OVER,
    CANCEL_REISSUED,
    CANCEL_VANISHED,
    PLAN_ACTIVE,
    PLAN_CANCELLED,
    ActualsExport,
    KittingHandover,
    Operator,
    Plan,
    RunCompletion,
    RunCorrection,
    RunEvent,
    RunInput,
    RunNgInput,
    SideLink,
)
from app.db.session import write_transaction
from app.services import audit
from app.services.completions import latest_completion
from app.services.errors import NotFound, RuleViolation
from app.services.plan_reconcile import kitting_nos_with_actuals

HISTORY_LIMIT = 50
_TABLES = (("run_events", RunEvent), ("run_inputs", RunInput), ("run_ng_inputs", RunNgInput),
           ("run_completions", RunCompletion), ("run_corrections", RunCorrection))


class CandidateOut(BaseModel):
    kitting_no: str
    issue_date: dt.date
    planned_start: dt.datetime | None
    planned_end: dt.datetime | None
    lot_nos: list[str]
    from_legacy: bool  # 既存アプリの判定(ビュー v_plan_stale の replacement)で出た候補
    has_actuals: bool  # すでに実績がある(選べない)


class HandoverItemOut(BaseModel):
    kitting_no: str
    file_no: str
    line_code: str
    run_no: int
    product_name: str
    lot_nos: list[str]
    reason: str  # stale(出し直しで古くなった)/ vanished(読めなくなった)/ reissued(出し直しで取消)
    completed: bool
    replacement_count: int  # 既存アプリの判定での候補の数(2以上は複数の候補)
    candidates: list[CandidateOut]


class HandoverHistoryOut(BaseModel):
    id: int
    old_kitting_no: str
    new_kitting_no: str
    confirmed_by: str
    confirmed_at: dt.datetime
    moved: dict[str, int]
    warnings: list[str]


class HandoverListOut(BaseModel):
    items: list[HandoverItemOut]
    history: list[HandoverHistoryOut]


class HandoverResultOut(BaseModel):
    old_kitting_no: str
    new_kitting_no: str
    moved: dict[str, int]
    warnings: list[str]


def _rows_by_kitting(session: Session, knos: set[str]) -> dict[str, list[Plan]]:
    out: dict[str, list[Plan]] = {}
    if not knos:
        return out
    for p in session.scalars(select(Plan).where(Plan.kitting_no.in_(knos)).order_by(Plan.kitting_no, Plan.lot_no)):
        out.setdefault(p.kitting_no, []).append(p)
    return out


def _reason(rows: list[Plan]) -> str | None:
    """引き継ぎの確認に出す理由。対象でなければ None。"""
    if any(p.status == PLAN_ACTIVE and p.is_stale for p in rows):
        return "stale"
    if all(p.status == PLAN_CANCELLED for p in rows):
        reasons = {p.cancel_reason or CANCEL_VANISHED for p in rows}
        if CANCEL_CARRIED_OVER in reasons:
            return None
        return CANCEL_REISSUED if CANCEL_REISSUED in reasons else CANCEL_VANISHED
    return None


def _candidates(session: Session, rows: list[Plan], with_actuals: set[str]) -> list[CandidateOut]:
    """移す先の候補: 既存アプリの判定(出し直し後のキッティングNo.)と、同じロットNo.・ファイルNo.・回の有効な計画。"""
    first = rows[0]
    lots = {p.lot_no for p in rows}
    legacy = {p.replacement_kitting_no for p in rows if p.replacement_kitting_no}
    stmt = select(Plan).where(Plan.status == PLAN_ACTIVE, Plan.kitting_no != first.kitting_no).where(
        (Plan.lot_no.in_(lots) & (Plan.file_no == first.file_no) & (Plan.run_no == first.run_no)) | Plan.kitting_no.in_(legacy))
    by_kno: dict[str, list[Plan]] = {}
    for p in session.scalars(stmt.order_by(Plan.kitting_no, Plan.lot_no)):
        by_kno.setdefault(p.kitting_no, []).append(p)
    return [
        CandidateOut(
            kitting_no=k, issue_date=ps[0].issue_date, planned_start=min((p.planned_start for p in ps if p.planned_start), default=None),
            planned_end=max((p.planned_end for p in ps if p.planned_end), default=None), lot_nos=[p.lot_no for p in ps],
            from_legacy=k in legacy, has_actuals=k in with_actuals,
        )
        for k, ps in by_kno.items()
    ]


def _done(session: Session) -> set[str]:
    return set(session.scalars(select(KittingHandover.old_kitting_no)))


def pending_items(session: Session) -> list[HandoverItemOut]:
    """引き継ぎの確認の一覧: 実績のある計画のうち、取り消された・古くなったもの(移す先の候補があるもの、または古い計画)。"""
    with_actuals = kitting_nos_with_actuals(session)
    items: list[HandoverItemOut] = []
    for kno, rows in sorted(_rows_by_kitting(session, with_actuals - _done(session)).items()):
        reason = _reason(rows)
        if reason is None:
            continue
        candidates = _candidates(session, rows, with_actuals)
        if not candidates and reason != "stale":
            continue
        first = rows[0]
        items.append(HandoverItemOut(
            kitting_no=kno, file_no=first.file_no, line_code=first.line_code, run_no=first.run_no, product_name=first.product_name,
            lot_nos=[p.lot_no for p in rows], reason=reason, completed=latest_completion(session, kno) is not None,
            replacement_count=max((p.replacement_count for p in rows), default=0), candidates=candidates,
        ))
    return items


def _who(session: Session, operator_id: int) -> str:
    op = session.get(Operator, operator_id)
    return f"{op.name}({op.worker_id})" if op and op.worker_id else (op.name if op else "")


def handover_list(session: Session) -> HandoverListOut:
    history = session.scalars(select(KittingHandover).order_by(KittingHandover.id.desc()).limit(HISTORY_LIMIT))
    return HandoverListOut(items=pending_items(session), history=[
        HandoverHistoryOut(id=h.id, old_kitting_no=h.old_kitting_no, new_kitting_no=h.new_kitting_no,
                           confirmed_by=_who(session, h.confirmed_by), confirmed_at=h.confirmed_at,
                           moved=json.loads(h.moved_json), warnings=json.loads(h.warnings_json))
        for h in history
    ])


def _warnings(session: Session, old: str, old_rows: list[Plan], new_rows: list[Plan]) -> list[str]:
    out: list[str] = []
    exported = list(session.scalars(select(ActualsExport.id).where(ActualsExport.content.contains(old))))
    if exported:
        ids = "、".join(str(i) for i in exported)
        out.append(f"書き出し済みの CSV(書き出し {ids})に、古いキッティングNo.の行があります。新しいキッティングNo.で書き出すと、"
                   f"既存アプリに二重に反映されるおそれがあります。既存アプリ側で確かめてください")
    new_lots = {p.lot_no for p in new_rows}
    ng_lots = set(session.scalars(select(RunNgInput.lot_no).where(RunNgInput.kitting_no == old)))
    if ng_lots - new_lots:
        out.append("NG数のロットNo.に、新しい計画に無いものがあります(" + "、".join(sorted(ng_lots - new_lots)) + ")")
    if session.scalars(select(SideLink.id).where((SideLink.side1_kitting_no == old) | (SideLink.side2_kitting_no == old))).first():
        out.append("「ひも付けの確認」の確定に、古いキッティングNo.があります。移したあとで確かめ直してください")
    if {p.lot_no for p in old_rows} != new_lots:
        out.append("古い計画と新しい計画で、ロットNo.の組が違います")
    return out


def confirm_handover(session: Session, admin: Operator, old_kno: str, new_kno: str) -> HandoverResultOut:
    """実績を新しいキッティングNo.へ移すと確定する。移す先に実績がある・候補にない場合は断る。"""
    with_actuals = kitting_nos_with_actuals(session)
    item = next((i for i in pending_items(session) if i.kitting_no == old_kno), None)
    if item is None:
        raise NotFound(f"引き継ぎの確認の対象に、キッティングNo. {old_kno} はありません(引き継ぎ済み、または対象ではありません)")
    if new_kno not in {c.kitting_no for c in item.candidates}:
        raise RuleViolation(f"キッティングNo. {new_kno} は、{old_kno} の移す先の候補にありません")
    if new_kno in with_actuals:
        raise RuleViolation(f"移す先 {new_kno} には、すでに実績があります。確定しません。"
                            f"合わせ方(どちらを残すか)は人が決め、実績を訂正してから、もう一度確定してください")
    old_rows = _rows_by_kitting(session, {old_kno})[old_kno]
    new_rows = _rows_by_kitting(session, {new_kno})[new_kno]
    warnings = _warnings(session, old_kno, old_rows, new_rows)
    now = clock.now()
    with write_transaction(session):
        moved = {name: session.execute(update(model).where(model.kitting_no == old_kno).values(kitting_no=new_kno)).rowcount
                 for name, model in _TABLES}
        # NG数の「NGが出た面の計画」が古いキッティングNo.の行も、新しいキッティングNo.に合わせる(書き出しで使う)
        moved["run_ng_inputs_side"] = session.execute(
            update(RunNgInput).where(RunNgInput.side_kitting_no == old_kno).values(side_kitting_no=new_kno)).rowcount
        for p in old_rows:
            p.status, p.cancel_reason, p.cancelled_at, p.updated_at = PLAN_CANCELLED, CANCEL_CARRIED_OVER, now, now
        session.add(KittingHandover(
            old_kitting_no=old_kno, new_kitting_no=new_kno, confirmed_by=admin.id, confirmed_at=now,
            moved_json=json.dumps(moved, ensure_ascii=False), warnings_json=json.dumps(warnings, ensure_ascii=False),
        ))
        audit.record_change(session, admin.id, "kitting_handovers", old_kno, "handover", {"kitting_no": old_kno},
                            {"kitting_no": new_kno, "moved": moved})
        session.commit()
    return HandoverResultOut(old_kitting_no=old_kno, new_kitting_no=new_kno, moved=moved, warnings=warnings)
