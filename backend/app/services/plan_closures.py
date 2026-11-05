"""計画終了: 始まっていない計画を、作業者が手で終わらせる(遅延して中止・計画変更・その他)。取り消すこともできる。

履歴(plan_closures)に1件ずつ足す(物理削除しない)。完了(片付けの終了)とは別の扱いで、実績の書き出し・生産記録票・効率には入らない。
工程の記録が1つでもある計画には使えない。詳細: docs/design/run-records.md(計画終了)
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_CANCELLED, Operator, Plan, PlanClosure, RunEvent
from app.services import audit
from app.services.errors import RuleViolation
from app.services.idempotency import run_idempotent
from app.services.kitting_plans import load_group


class ClosureReason(StrEnum):
    DELAY_STOP = "delay_stop"  # 遅延して中止
    PLAN_CHANGE = "plan_change"  # 計画変更
    OTHER = "other"  # その他(文で入れる。必須)


class ClosureOut(BaseModel):
    reason: str
    note: str | None
    closed_by_name: str | None
    closed_at: dt.datetime


class ClosureResultOut(BaseModel):
    kitting_no: str
    closed: bool
    closure: ClosureOut | None


def closures_of(session: Session, kitting_nos: list[str]) -> dict[str, PlanClosure]:
    """計画終了している(すべてのロットで、最後の行が close の)キッティングNo.と、その最後の close の行。"""
    if not kitting_nos:
        return {}
    rows = session.scalars(select(PlanClosure).where(PlanClosure.kitting_no.in_(kitting_nos)).order_by(PlanClosure.id)).all()
    latest: dict[tuple[str, str], PlanClosure] = {(r.kitting_no, r.lot_no): r for r in rows}
    lots: dict[str, set[str]] = {}
    for kno, lot in session.execute(select(Plan.kitting_no, Plan.lot_no).where(Plan.kitting_no.in_(kitting_nos))):
        lots.setdefault(kno, set()).add(lot)
    out: dict[str, PlanClosure] = {}
    for kno, lot_set in lots.items():
        rep = [latest.get((kno, lot)) for lot in lot_set]
        if rep and all(r is not None and r.action == "close" for r in rep):
            out[kno] = max(rep, key=lambda r: r.id)  # type: ignore[arg-type, return-value]
    return out


def closed_kitting_nos(session: Session) -> set[str]:
    """計画終了している、すべてのキッティングNo.。"""
    kittings = list(session.scalars(select(PlanClosure.kitting_no).distinct()))
    return set(closures_of(session, kittings))


def closure_out(session: Session, row: PlanClosure | None) -> ClosureOut | None:
    if row is None:
        return None
    who = session.get(Operator, row.operator_id)
    return ClosureOut(reason=row.reason or "", note=row.note, closed_by_name=who.name if who else None, closed_at=row.created_at)


def ensure_not_closed(session: Session, kitting_no: str) -> None:
    """工程を始める・押し忘れを足すときの確認。計画終了した計画には記録できない。"""
    if kitting_no in closures_of(session, [kitting_no]):
        raise RuleViolation("計画終了した計画です。工程を始めるには、先に「計画終了を取り消す」を押してください")


def _lot_nos(session: Session, kitting_no: str) -> list[str]:
    return sorted(session.scalars(select(Plan.lot_no).where(Plan.kitting_no == kitting_no)))


def _write(session: Session, kitting_no: str, operator_id: int, action: str, reason: str | None, note: str | None, now: dt.datetime) -> PlanClosure:
    rows = [PlanClosure(kitting_no=kitting_no, lot_no=lot, action=action, reason=reason, note=note, operator_id=operator_id, created_at=now)
            for lot in _lot_nos(session, kitting_no)]
    session.add_all(rows)
    session.flush()
    audit.record_change(
        session, operator_id, "plan_closures", kitting_no, "plan_close" if action == "close" else "plan_close_cancel",
        {"closed": action != "close"}, {"closed": action == "close", "lots": [r.lot_no for r in rows], "note": note}, reason=reason,
    )
    return rows[0]


def close_plan(session: Session, kitting_no: str, operator_id: int, reason: str, note: str | None, request_id: str) -> ClosureResultOut:
    """計画終了にする。始まっていない(取り消していない工程の記録が無い)・取消でない・まだ計画終了していない計画だけ。"""
    payload = {"kitting_no": kitting_no, "operator_id": operator_id, "reason": reason, "note": note}

    def action(now: dt.datetime) -> ClosureResultOut:
        try:
            code = ClosureReason(reason)
        except ValueError:
            raise RuleViolation("理由を選んでください(遅延して中止・計画変更・その他)") from None
        text = (note or "").strip() or None
        if code == ClosureReason.OTHER and text is None:
            raise RuleViolation("理由が「その他」のときは、内容を記入してください")
        group = load_group(session, kitting_no)
        if group.status == PLAN_CANCELLED:
            raise RuleViolation("取消になった計画は、計画終了にできません")
        started = session.scalars(select(RunEvent.id).where(RunEvent.kitting_no == kitting_no, RunEvent.voided_at.is_(None)).limit(1)).first()
        if started is not None:
            raise RuleViolation("作業が始まっている計画は、計画終了にできません")
        if kitting_no in closures_of(session, [kitting_no]):
            raise RuleViolation("すでに計画終了しています")
        row = _write(session, kitting_no, operator_id, "close", code.value, text, now)
        return ClosureResultOut(kitting_no=kitting_no, closed=True, closure=closure_out(session, row))

    return run_idempotent(session, request_id, "plan.close", payload, ClosureResultOut, action)


def cancel_close(session: Session, kitting_no: str, operator_id: int, request_id: str) -> ClosureResultOut:
    """計画終了を取り消す(取り消しの行を足す)。計画終了していない計画は断る。"""
    payload = {"kitting_no": kitting_no, "operator_id": operator_id}

    def action(now: dt.datetime) -> ClosureResultOut:
        load_group(session, kitting_no)
        if kitting_no not in closures_of(session, [kitting_no]):
            raise RuleViolation("計画終了していません")
        _write(session, kitting_no, operator_id, "cancel", None, None, now)
        return ClosureResultOut(kitting_no=kitting_no, closed=False, closure=None)

    return run_idempotent(session, request_id, "plan.close.cancel", payload, ClosureResultOut, action)
