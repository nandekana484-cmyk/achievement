"""アプリの入口。

1プロセスで、APIとビルド済みの画面(frontend/dist)をまとめて配信する。
起動: uvicorn app.main:app --port 8000(backend フォルダで実行)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import health, plans
from app.core.config import get_config
from app.db.migrate import upgrade_to_head
from app.db.session import get_sessionmaker, init_db
from app.services.plan_sync_scheduler import PlanSyncScheduler

logger = logging.getLogger(__name__)

# 画面のビルド成果物。exe化したときは packaging 側で同梱先を GENBA_STATIC_DIR に渡す。
STATIC_DIR = Path(
    os.environ.get("GENBA_STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist")
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config = get_config()
    engine = init_db(config.paths.database)
    upgrade_to_head(engine)

    scheduler: PlanSyncScheduler | None = None
    if config.paths.legacy_database is None:
        logger.info("paths.legacy_database が未設定のため、計画の同期はしません")
    else:
        scheduler = PlanSyncScheduler(get_sessionmaker(), config.paths.legacy_database, config.sync)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
        engine.dispose()


app = FastAPI(title="現場実績入力", version=__version__, lifespan=lifespan)
app.include_router(health.router)
app.include_router(plans.router)

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        """APIと静的ファイル以外のURLは、すべて画面(index.html)に渡す。"""
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
