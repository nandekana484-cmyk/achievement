"""計画の同期の警告の記録(plan_sync_warnings)。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PlanSyncWarning
from app.integration.legacy_plans import ReadWarning


def update_warnings(session: Session, warnings: list[ReadWarning], now: datetime) -> None:
    """警告を (kitting_no, lot_no, message) ごとに1件にまとめて記録する。

    出続けている警告は last_seen_at を更新し、出なくなったら resolved_at を入れ、再び出たら空に戻す。
    """
    existing: dict[tuple, PlanSyncWarning] = {}
    for row in session.scalars(select(PlanSyncWarning).order_by(PlanSyncWarning.id)):
        existing[(row.kitting_no, row.lot_no, row.message)] = row

    seen: set[tuple] = set()
    for w in warnings:
        key = (w.kitting_no, w.lot_no, w.message)
        if key in seen:
            continue
        seen.add(key)
        row = existing.get(key)
        if row is None:
            session.add(PlanSyncWarning(
                kitting_no=w.kitting_no, lot_no=w.lot_no, message=w.message,
                legacy_plan_item_id=w.legacy_plan_item_id, first_seen_at=now, last_seen_at=now,
            ))
        else:
            row.legacy_plan_item_id = w.legacy_plan_item_id
            row.last_seen_at = now
            row.resolved_at = None

    for key, row in existing.items():
        if key not in seen and row.resolved_at is None:
            row.resolved_at = now
