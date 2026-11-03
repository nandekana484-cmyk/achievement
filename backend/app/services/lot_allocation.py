"""ロットへの割り振り(キッティングNo.ごとの生産数の合計を、ロットに分けた値)の保存と読み方。

優先順位: 保存した割り振り > 今の規則(domain/allocation.py)。保存した割り振りの合計が今の生産数の合計と合わない
(保存のあとに生産数が訂正された)ときや、ロットの組が違うときは、保存したものを使わず今の規則で計算し、「直す必要がある」(stale)にする。
保存・元に戻す・引き継ぎは履歴(lot_allocation_changes)に追加するだけで、audit_log にも残す。実績の記録は変えない。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import LotAllocationChange
from app.domain.allocation import allocate, balance
from app.services import audit
from app.services.completions import latest_completion, produced_total
from app.services.errors import RuleViolation
from app.services.idempotency import run_idempotent
from app.services.kitting_plans import KittingGroup, load_group
from app.services.side_link_export import last_export_at

ACTION_SAVE, ACTION_RESET = "save", "reset"
ACTION_HANDOVER_IN, ACTION_HANDOVER_OUT = "handover_in", "handover_out"
_SAVED_ACTIONS = (ACTION_SAVE, ACTION_HANDOVER_IN)
STALE_MESSAGE = "割り振りを直す必要があります"


@dataclass
class Effective:
    qtys: list[int]  # 計画のロットの順
    saved: bool  # 保存した割り振りを使っている
    stale: bool  # 保存した割り振りがあるが、合わないので今の規則で計算した


def _load(row: LotAllocationChange | None) -> dict[str, int] | None:
    if row is None or row.action not in _SAVED_ACTIONS or not row.after_json:
        return None
    return {k: int(v) for k, v in json.loads(row.after_json).items()}


def latest_change(session: Session, kitting_no: str) -> LotAllocationChange | None:
    return session.scalars(select(LotAllocationChange).where(LotAllocationChange.kitting_no == kitting_no)
                           .order_by(LotAllocationChange.id.desc())).first()


def effective(session: Session, group: KittingGroup, total: int) -> Effective:
    """そのキッティングNo.のロットごとの割り振り(保存したものが合えばそれ、無ければ今の規則)。"""
    planned = [lot.planned_qty for lot in group.lots]
    saved = _load(latest_change(session, group.kitting_no))
    if saved is not None:
        lots = [lot.lot_no for lot in group.lots]
        if set(saved) == set(lots) and sum(saved.values()) == total:
            return Effective([saved[no] for no in lots], saved=True, stale=False)
        return Effective(allocate(total, planned), saved=False, stale=True)
    return Effective(allocate(total, planned), saved=False, stale=False)


class AllocLotOut(BaseModel):
    lot_no: str
    planned_qty: int
    qty: int  # 今の割り振り(「差を引くロット」の提案のときは、提案の値)


class AllocationOut(BaseModel):
    kitting_no: str
    total: int  # 生産数の合計
    planned_total: int
    saved: bool  # 保存した割り振りを使っている
    stale: bool  # 保存した割り振りが合わないので、今の規則で計算している(「割り振りを直す必要があります」)
    editable: bool  # 割り振りの画面を出す(ロットが2つ以上、完了していて、合計が計画数の合計と違う。保存したものがあるときも)
    exported: bool  # 書き出し済み(変えたら、既存アプリの値は管理者が直す)
    exported_at: dt.datetime | None
    lots: list[AllocLotOut]
    proposal_error: str | None = None  # 「差を引くロット」の提案ができないとき(0 未満になる)


def allocation_out(session: Session, group: KittingGroup, balance_lot_no: str | None = None) -> AllocationOut:
    total = produced_total(session, group.kitting_no)
    eff = effective(session, group, total)
    planned = [lot.planned_qty for lot in group.lots]
    qtys, error = eff.qtys, None
    if balance_lot_no is not None:
        index = next((i for i, lot in enumerate(group.lots) if lot.lot_no == balance_lot_no), None)
        if index is None:
            raise RuleViolation(f"ロットNo. {balance_lot_no} は、この計画にありません")
        proposal = balance(total, planned, index)
        if proposal is None:
            error = f"ロットNo. {balance_lot_no} で差を引くと、0 未満になります。数を直接直してください"
        else:
            qtys = proposal
    exported_at = last_export_at(session, {group.kitting_no})
    done = latest_completion(session, group.kitting_no) is not None
    return AllocationOut(
        kitting_no=group.kitting_no, total=total, planned_total=sum(planned), saved=eff.saved, stale=eff.stale,
        editable=done and len(group.lots) >= 2 and (total != sum(planned) or eff.saved or eff.stale),
        exported=exported_at is not None, exported_at=exported_at,
        lots=[AllocLotOut(lot_no=lot.lot_no, planned_qty=lot.planned_qty, qty=q) for lot, q in zip(group.lots, qtys, strict=True)],
        proposal_error=error)


def _check(session: Session, group: KittingGroup, quantities: dict[str, int]) -> None:
    if latest_completion(session, group.kitting_no) is None:
        raise RuleViolation("片付けが終わった計画だけ、割り振りを保存できます")
    if set(quantities) != {lot.lot_no for lot in group.lots}:
        raise RuleViolation("割り振りのロットが、計画のロットと合いません。画面を読み直してください")
    if any(q < 0 for q in quantities.values()):
        raise RuleViolation("割り振りの数は 0 以上にしてください")
    total = produced_total(session, group.kitting_no)
    if sum(quantities.values()) != total:
        raise RuleViolation(f"ロットの数の合計({sum(quantities.values())})が、生産数の合計({total})と一致しません")


def current_values(session: Session, group: KittingGroup) -> dict[str, int]:
    eff = effective(session, group, produced_total(session, group.kitting_no))
    return {lot.lot_no: q for lot, q in zip(group.lots, eff.qtys, strict=True)}


def _add(session: Session, actor_id: int, source: str, kno: str, action: str, before: dict[str, int], after: dict[str, int],
         exported_at: dt.datetime | None) -> None:
    session.add(LotAllocationChange(
        kitting_no=kno, action=action, source=source, changed_by=actor_id, changed_at=clock.now(),
        before_json=json.dumps(before, ensure_ascii=False), after_json=json.dumps(after, ensure_ascii=False), exported_at=exported_at))
    audit.record_change(session, actor_id, "lot_allocations", kno, action, before, after, None)


def apply_save(session: Session, actor_id: int, source: str, group: KittingGroup, quantities: dict[str, int],
               *, mark_exported: bool = True) -> bool:
    """保存する(トランザクションの中で呼ぶ)。保存済みの値と同じなら何もしない(False)。

    mark_exported=False は、今まさに書き出す値の保存(書き出しの画面。変更は書き出す CSV に入るので、「書き出し後の変更」にしない)。
    """
    _check(session, group, quantities)
    before = current_values(session, group)
    if quantities == before and effective(session, group, sum(before.values())).saved:
        return False
    _add(session, actor_id, source, group.kitting_no, ACTION_SAVE, before, quantities,
         last_export_at(session, {group.kitting_no}) if mark_exported else None)
    return True


class _Saved(BaseModel):
    allocation: AllocationOut


def save(session: Session, actor_id: int, source: str, kitting_no: str, quantities: dict[str, int], request_id: str) -> AllocationOut:
    """現場からの保存(作業者ID必須。同じ request_id の再送には最初の応答を返す)。"""
    def action(_now: dt.datetime) -> _Saved:
        group = load_group(session, kitting_no)
        apply_save(session, actor_id, source, group, quantities)
        return _Saved(allocation=allocation_out(session, group))

    payload = {"kitting_no": kitting_no, "quantities": quantities, "actor": actor_id, "source": source}
    return run_idempotent(session, request_id, "lot_allocation.save", payload, _Saved, action).allocation


def reset(session: Session, actor_id: int, source: str, kitting_no: str, request_id: str) -> AllocationOut:
    """保存した割り振りを外して、今の規則に戻す。"""
    def action(_now: dt.datetime) -> _Saved:
        group = load_group(session, kitting_no)
        if _load(latest_change(session, kitting_no)) is None:
            raise RuleViolation("保存した割り振りがありません")
        before = current_values(session, group)
        rule = allocate(produced_total(session, kitting_no), [lot.planned_qty for lot in group.lots])
        after = {lot.lot_no: q for lot, q in zip(group.lots, rule, strict=True)}
        _add(session, actor_id, source, kitting_no, ACTION_RESET, before, after, last_export_at(session, {kitting_no}))
        return _Saved(allocation=allocation_out(session, group))

    payload = {"kitting_no": kitting_no, "actor": actor_id, "source": source}
    return run_idempotent(session, request_id, "lot_allocation.reset", payload, _Saved, action).allocation


def move_allocation(session: Session, admin_id: int, old: str, new: str) -> None:
    """引き継ぎで実績を新しいキッティングNo.へ移したとき、保存した割り振りも移す(トランザクションの中で呼ぶ)。"""
    saved = _load(latest_change(session, old))
    if saved is None:
        return
    _add(session, admin_id, "admin", new, ACTION_HANDOVER_IN, {}, saved, last_export_at(session, {old, new}))
    _add(session, admin_id, "admin", old, ACTION_HANDOVER_OUT, saved, {}, None)
