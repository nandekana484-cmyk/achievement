"""丁取り(master.db のビュー v_board_teitori)を、本アプリの board_teitori に反映する。計画の同期の書き込みの中で呼ぶ。

- ビューの全行を上書きする。ビューから消えた組の行は消さない(前の値が残る)
- ビューが無い・読めないときは、同期全体を失敗にせず、前回の値を使って警告を1回出す
詳細: docs/design/metrics.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BoardTeitori
from app.integration.legacy_plans import LegacySourceError, LegacyTeitori, ReadWarning, read_master_teitori

logger = logging.getLogger(__name__)

NO_TEITORI_VIEW = ("master.db に丁取りのビュー(v_board_teitori)がありません。丁取りは前回の値を使います"
                   "(既存アプリを 4.1.0 以降にしてください)")

_last_message: str | None = None  # 警告を出した理由。同じ理由はログに1回だけ出す(同期は60秒ごと)


@dataclass(frozen=True)
class TeitoriRead:
    rows: list[LegacyTeitori] | None  # None = 読めなかった(ビューが無い、またはDBを読めない)
    message: str = ""  # 警告の文(画面に出してよい)
    detail: str = ""  # ログだけに出す詳細


def read_teitori_for_sync(legacy_app_dir: Path) -> TeitoriRead:
    """丁取りを計画とは切り離して読む。"""
    try:
        rows = read_master_teitori(legacy_app_dir)
    except LegacySourceError as e:
        return TeitoriRead(None, f"{e.public}。丁取りは前回の値を使います", str(e))
    return TeitoriRead(rows, NO_TEITORI_VIEW) if rows is None else TeitoriRead(rows)


def sync_teitori(session: Session, read: TeitoriRead, now: datetime) -> list[ReadWarning]:
    """丁取りを反映し、警告を返す(コミットは呼び出し側)。読めなかったときは何も書かず、警告だけ返す。"""
    global _last_message  # noqa: PLW0603
    if read.rows is None:
        if _last_message != read.message:
            logger.warning("%s%s", read.message, f"({read.detail})" if read.detail else "")
            _last_message = read.message
        return [ReadWarning(None, None, read.message)]
    _last_message = None
    existing = {(r.setup_file_no, r.mounting_line): r for r in session.scalars(select(BoardTeitori))}
    for t in read.rows:
        row = existing.get((t.setup_file_no, t.mounting_line))
        if row is None:
            row = BoardTeitori(setup_file_no=t.setup_file_no, mounting_line=t.mounting_line)
            session.add(row)
        row.teitori, row.status, row.part_no, row.fetched_at, row.synced_at = t.teitori, t.status, t.part_no, t.fetched_at, now
    return []
