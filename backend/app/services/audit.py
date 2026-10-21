"""変更の記録(audit_log)。誰が、いつ、何を、変更前と変更後。書き込みのトランザクションの中で呼ぶ(コミットは呼び出し側)。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import AuditLog


def record_change(
    session: Session, actor_id: int | None, table: str, key: str, action: str,
    before: dict[str, Any] | None, after: dict[str, Any], reason: str | None = None,
) -> AuditLog:
    row = AuditLog(
        changed_at=clock.now(), changed_by=actor_id, target_table=table, target_key=key, action=action,
        before_json=json.dumps(before, ensure_ascii=False) if before is not None else None,
        after_json=json.dumps(after, ensure_ascii=False), reason=reason,
    )
    session.add(row)
    return row


def diff_fields(row: object, changes: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """changes のうち、今の値と違う項目だけの変更前と変更後。"""
    before = {k: getattr(row, k) for k, v in changes.items() if getattr(row, k) != v}
    return before, {k: changes[k] for k in before}
