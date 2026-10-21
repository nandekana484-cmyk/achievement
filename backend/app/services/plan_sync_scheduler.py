"""計画の同期の定期実行。

- main.py の lifespan で start() / stop() する asyncio のタスク
- 同期処理は別スレッドで実行し、イベントループ(APIの応答)を止めない
- 同期は同時に1つだけ。実行中に次が来たら skipped として記録する
- 1回の失敗で止めず、次の回も実行する
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import SyncConfig
from app.services.plan_sync import PlanSyncResult, record_skipped, run_plan_sync

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def run_plan_sync_exclusive(
    session_factory: sessionmaker[Session], legacy_app_dir: Path, sync_config: SyncConfig | None = None
) -> PlanSyncResult:
    """同期を1回行う。ほかの同期が実行中なら、実行せずに skipped を記録する。"""
    if not _lock.acquire(blocking=False):
        with session_factory() as session:
            return record_skipped(session, "前回の同期が実行中のため、今回は実行しませんでした")
    try:
        with session_factory() as session:
            return run_plan_sync(session, legacy_app_dir, sync_config)
    finally:
        _lock.release()


class PlanSyncScheduler:
    def __init__(self, session_factory: sessionmaker[Session], legacy_app_dir: Path, sync_config: SyncConfig) -> None:
        self._session_factory = session_factory
        self._legacy_app_dir = legacy_app_dir
        self._sync_config = sync_config
        self._interval_sec = sync_config.plan_interval_sec
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="plan-sync")
            logger.info("計画の同期を開始します(%s 秒ごと、既存アプリのフォルダ: %s)", self._interval_sec, self._legacy_app_dir)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(
                    run_plan_sync_exclusive, self._session_factory, self._legacy_app_dir, self._sync_config
                )
            except Exception:  # noqa: BLE001  次の回は実行する
                logger.exception("計画の同期で想定外のエラーが起きました")
            await asyncio.sleep(self._interval_sec)
