"""NG数(ロットと、NGが出た面を選んで入力する)。

選べる面: 面1の計画では面1だけ。面2の計画では面2と、同じロットNo.・同じファイルNo.の面1の計画が見つかるときの面1。
同じ (入力した計画のキッティングNo., ロットNo., 面) の入力は、最新の値を有効とする(過去の値は履歴として残す)。
詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, Plan, RunNgInput
from app.services.errors import RuleViolation
from app.services.idempotency import run_idempotent
from app.services.kitting_plans import KittingGroup, load_group
from app.services.line_operators import resolve_recorder
from app.services.plan_views import NgChoiceOut
from app.services.views import NgEntryOut, NgInputOut, ng_entry_out, ng_input_out

NO_SIDE1_PLAN = "同じロットの面1の計画が見つからないため、面1は選べません"


def side1_plan(session: Session, lot_no: str, file_no: str) -> Plan | None:
    """面2の計画のロットに対応する、面1の計画(同じロットNo.・同じファイルNo.)。"""
    return session.scalars(
        select(Plan).where(Plan.lot_no == lot_no, Plan.file_no == file_no, Plan.run_no == 1, Plan.status == PLAN_ACTIVE)
        .order_by(Plan.planned_start, Plan.kitting_no)
    ).first()


def ng_choices(session: Session, group: KittingGroup) -> list[NgChoiceOut]:
    choices = []
    for lot in group.lots:
        if group.run_no == 1:
            choices.append(NgChoiceOut(lot_no=lot.lot_no, sides=[1], side1_kitting_no=None, note=None))
            continue
        p1 = side1_plan(session, lot.lot_no, group.file_no)
        choices.append(NgChoiceOut(
            lot_no=lot.lot_no, sides=[1, 2] if p1 else [2], side1_kitting_no=p1.kitting_no if p1 else None,
            note=None if p1 else NO_SIDE1_PLAN,
        ))
    return choices


def latest_ng(session: Session, kitting_no: str) -> list[NgEntryOut]:
    """入力した計画の、ロットと面ごとの最新のNG数(ロットNo.・面の順)。"""
    rows = session.scalars(
        select(RunNgInput).where(RunNgInput.kitting_no == kitting_no).order_by(RunNgInput.entered_at, RunNgInput.id)
    )
    latest: dict[tuple[str, int], RunNgInput] = {}
    for r in rows:
        latest[(r.lot_no, r.side)] = r
    return [ng_entry_out(session, latest[k]) for k in sorted(latest)]


def _side_kitting_no(session: Session, group: KittingGroup, lot_no: str, side: int) -> str:
    """NGが出た面の計画のキッティングNo.。選べない面なら RuleViolation。"""
    if lot_no not in {lot.lot_no for lot in group.lots}:
        raise RuleViolation(f"ロットNo. {lot_no} は、この計画のロットではありません")
    if side not in (1, 2):
        raise RuleViolation("面は1か2を選んでください")
    if side == group.run_no:
        return group.kitting_no
    if group.run_no == 1:
        raise RuleViolation("面1の計画では、面2のNGは入力できません")
    p1 = side1_plan(session, lot_no, group.file_no)
    if p1 is None:
        raise RuleViolation(NO_SIDE1_PLAN)
    return p1.kitting_no


def set_ng_qty(
    session: Session, kitting_no: str, lot_no: str, side: int, ng_qty: int, request_id: str,
    operator_id: int | None = None,
) -> NgInputOut:
    """NG数を入力する。行を追加し、同じロット・面では最新の値を有効とする。"""
    payload = {"kitting_no": kitting_no, "lot_no": lot_no, "side": side, "ng_qty": ng_qty, "operator_id": operator_id}

    def action(now: datetime) -> NgInputOut:
        if ng_qty < 0:
            raise RuleViolation("NG数は0以上の整数で入力してください")
        group = load_group(session, kitting_no)
        side_kno = _side_kitting_no(session, group, lot_no, side)
        recorder = resolve_recorder(session, group.line_code, operator_id)
        row = RunNgInput(kitting_no=kitting_no, lot_no=lot_no, side=side, side_kitting_no=side_kno, ng_qty=ng_qty,
                         entered_by=recorder, entered_at=now, request_id=request_id)
        session.add(row)
        session.flush()
        return ng_input_out(session, row)

    return run_idempotent(session, request_id, "run.ng_qty", payload, NgInputOut, action)
