"""既存アプリの作業者(master.db の workers)を、本アプリの operators に反映する。計画の同期の書き込みの中で呼ぶ。

- 既存アプリにある作業者: 名前・役割・有効/無効を既存アプリに合わせる(作業者IDは既存アプリの表記のまま)
- 既存アプリから見えなくなった作業者: 消さずに無効にする(過去の記録が参照しているため)
- 作業者IDが正規化すると重なる場合: 表記の順で最初の1人だけ取り込み、ほかは取り込まずに警告を出す
- 計画の同期が失敗した回(計画の表が無いなど)でも、作業者は読み込む(sync_operators_alone)
詳細: docs/design/run-records.md
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Operator
from app.db.session import write_transaction
from app.domain.worker_id import worker_key
from app.integration.legacy.workers import LegacyWorker
from app.integration.legacy_plans import ReadWarning

logger = logging.getLogger(__name__)

SOURCE_LEGACY = "legacy"
SOURCE_LOCAL = "local"


def _unique_workers(workers: list[LegacyWorker]) -> tuple[dict[str, LegacyWorker], list[ReadWarning]]:
    kept: dict[str, LegacyWorker] = {}
    warnings: list[ReadWarning] = []
    for w in sorted(workers, key=lambda x: x.worker_id):
        key = worker_key(w.worker_id)
        if key in kept:
            warnings.append(ReadWarning(None, None, (
                f"作業者ID「{w.worker_id}」は「{kept[key].worker_id}」と、全角・半角や大文字・小文字の違いを除くと同じです。"
                f"「{w.worker_id}」は取り込みません"
            )))
            continue
        kept[key] = w
    return kept, warnings


def sync_operators(session: Session, workers: list[LegacyWorker]) -> list[ReadWarning]:
    """作業者を反映し、警告を返す(コミットは呼び出し側)。"""
    kept, warnings = _unique_workers(workers)
    existing = {op.worker_key: op for op in session.scalars(select(Operator).where(Operator.worker_key.is_not(None)))}

    for key, w in kept.items():
        op = existing.get(key)
        if op is not None and op.source != SOURCE_LEGACY:
            warnings.append(ReadWarning(None, None, (
                f"作業者ID「{w.worker_id}」は、開発用に足した作業者と重なるため取り込みません"
            )))
            continue
        if op is None:
            op = Operator(source=SOURCE_LEGACY, worker_key=key, sort_order=0)
            session.add(op)
        op.worker_id, op.name, op.role, op.active = w.worker_id, w.name, w.role, w.active

    for key, op in existing.items():
        if op.source == SOURCE_LEGACY and key not in kept:
            op.active = False  # 既存アプリから見えなくなった(消さずに無効にする)
    return warnings


def sync_operators_alone(session: Session, workers: list[LegacyWorker] | None) -> None:
    """計画の同期が失敗した回でも、作業者だけは反映する。警告の記録は変えず(読めなかった回のため)、ログに出す。"""
    if workers is None:
        return
    try:
        with write_transaction(session):
            for w in sync_operators(session, workers):
                logger.warning("作業者の読み込み: %s", w.message)
            session.commit()
    except Exception:  # noqa: BLE001  同期の失敗の記録を止めない
        session.rollback()
        logger.exception("作業者の読み込みに失敗しました")
