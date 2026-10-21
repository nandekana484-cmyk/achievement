"""既存アプリの作業者(master.db の workers)を読み取り専用で読む。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.integration.legacy.readonly import open_readonly


@dataclass(frozen=True)
class LegacyWorker:
    worker_id: str  # 既存アプリの表記のまま
    name: str
    role: str  # admin / operator
    active: bool


def read_workers(master_db_path: Path) -> list[LegacyWorker] | None:
    """workers 表のすべての行(無効な作業者も含む)。表が無い master.db なら None。"""
    conn = open_readonly(master_db_path)
    try:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workers'").fetchone() is None:
            return None
        rows = conn.execute("SELECT worker_id, name, role, is_active FROM workers ORDER BY worker_id").fetchall()
    finally:
        conn.close()
    return [
        LegacyWorker(
            worker_id=str(r["worker_id"]), name=(r["name"] or "").strip(), role=(r["role"] or "operator").strip(),
            active=bool(r["is_active"]) if r["is_active"] is not None else True,
        )
        for r in rows if r["worker_id"] is not None and str(r["worker_id"]).strip()
    ]
