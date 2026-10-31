"""計画の同期で、本アプリの plans に行う変更(追加・変更・取消・復活)を決めて書く。詳細: docs/design/legacy-integration.md

取消の判定は plan_cancel.py(読めなくなった)と plan_reconcile.py(出し直しで古くなった)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import SyncConfig
from app.db.models import CANCEL_REISSUED, CANCEL_VANISHED, PLAN_ACTIVE, PLAN_CANCELLED, Plan
from app.integration.legacy_plans import LegacyPlan, ReadWarning
from app.services.kitting_plans import group_lots
from app.services.plan_cancel import cancel_guard_reason, count_cancellable, plans_to_cancel
from app.services.plan_diff import CarryoverCandidate, PlanDiff, PlanKey, diff_plans
from app.services.plan_reconcile import Reconcile, apply_stale_flags, kitting_nos_with_actuals, reconcile_stale
from app.services.plan_rows import apply_plan, apply_tracking, to_legacy
from app.services.plan_source import SourceSelection

logger = logging.getLogger(__name__)


@dataclass
class Changes:
    """本アプリの計画に対して、この同期で行う変更。"""

    rows: dict[PlanKey, Plan]
    diff: PlanDiff
    incoming: dict[PlanKey, LegacyPlan]
    removed: list[PlanKey]  # 読めなくなった計画の取消
    reissued: list[PlanKey]  # 出し直しで古くなった計画の取消(実績が無いもの)
    reconcile: Reconcile
    warnings: list[ReadWarning]
    carryovers: list[CarryoverCandidate]
    guard: str | None

    @property
    def cancelled_count(self) -> int:
        return len(self.removed) + len(self.reissued)


def plan_changes(session: Session, sel: SourceSelection, cfg: SyncConfig) -> Changes:
    """本アプリの計画と比べて、追加・変更・取消と、安全装置に当たるかを決める(まだ書き込まない)。"""
    rows = {(p.kitting_no, p.lot_no): p for p in session.scalars(select(Plan))}
    with_actuals = kitting_nos_with_actuals(session)
    keys_with_actuals = {key for key in rows if key[0] in with_actuals}
    recon = reconcile_stale(rows, sel, with_actuals)
    # 出し直しで取り消す計画は「既存DBから消えた」のではないので、読めなくなった計画の判定には渡さない
    reissue_keys = set(recon.cancel)
    current = {key: to_legacy(p) for key, p in rows.items() if p.status == PLAN_ACTIVE and key not in reissue_keys}
    live_plans = [p for p in sel.plans if p.key not in recon.exclude]
    diff = diff_plans(current, live_plans, keys_with_actuals)
    incoming = {p.key: p for p in live_plans}

    today_start = datetime.combine(clock.now().date(), time(), tzinfo=clock.JST)
    removed, warnings = plans_to_cancel(
        diff.removed_without_actuals + diff.removed_with_actuals, rows, incoming, sel, today_start,
    )
    warnings += recon.warnings
    warnings += [ReadWarning(None, g.kitting_no, message) for g in group_lots(sel.plans) for message in g.warnings]
    removed_set = set(removed)
    # 安全装置の件数には、出し直しの取消も入れる。出し直しは計画終了が過去でも取り消すので、分母にも同じものを入れる
    active = count_cancellable(current.values(), today_start) + len(recon.cancel)
    changes = Changes(
        rows=rows, diff=diff, incoming=incoming, removed=removed, reissued=list(recon.cancel), reconcile=recon,
        warnings=warnings, carryovers=[c for c in diff.carryovers if c.old_key in removed_set], guard=None,
    )
    changes.guard = cancel_guard_reason(changes.cancelled_count, active, cfg)
    return changes


def write_changes(session: Session, changes: Changes, sel: SourceSelection, now: datetime) -> tuple[int, int]:
    """追加・変更・取消を本アプリの plans に書く。追加した件数と、取消から戻った件数を返す。"""
    rows, diff = changes.rows, changes.diff
    added = revived = 0
    for plan in diff.added:
        row = rows.get(plan.key)
        if row is None:
            row = Plan(kitting_no=plan.kitting_no, lot_no=plan.lot_no, first_seen_at=now)
            session.add(row)
            added += 1
        else:
            logger.info("取消になっていた計画が既存DBに戻りました: %s", plan.key)
            revived += 1
        apply_plan(row, plan, sel.plan_sources[plan.key])
        row.status = PLAN_ACTIVE
        row.cancelled_at = None
        row.cancel_reason = None
        row.updated_at = now
        apply_stale_flags(row, sel.stale.get(plan.key))

    for plan in diff.changed:
        apply_plan(rows[plan.key], plan, sel.plan_sources[plan.key])
        rows[plan.key].updated_at = now
        apply_stale_flags(rows[plan.key], sel.stale.get(plan.key))

    for key in diff.unchanged:
        # 内容は同じでも、行番号・版・正とするDBは変わることがある
        apply_tracking(rows[key], changes.incoming[key], sel.plan_sources[key])
        apply_stale_flags(rows[key], sel.stale.get(key))

    _cancel(rows, changes.removed, CANCEL_VANISHED, now)
    _cancel(rows, changes.reissued, CANCEL_REISSUED, now)
    for key in changes.reissued:
        apply_stale_flags(rows[key], sel.stale.get(key))
    return added, revived


def _cancel(rows: dict[PlanKey, Plan], keys: list[PlanKey], reason: str, now: datetime) -> None:
    for key in keys:
        rows[key].status = PLAN_CANCELLED
        rows[key].cancel_reason = reason
        rows[key].cancelled_at = now
        rows[key].updated_at = now
