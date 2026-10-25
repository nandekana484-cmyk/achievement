"""アプリの入口。

1プロセスで、APIとビルド済みの画面(frontend/dist)をまとめて配信する。
起動: uvicorn app.main:app --port 8000(backend フォルダで実行)。exe の入口は app/server.py
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api import admin, admin_actuals, admin_masters, admin_reports, corrections, health, lines, plans, runs
from app.core.config import get_config, is_frozen
from app.db.migrate import upgrade_to_head
from app.db.session import get_sessionmaker, init_db
from app.services.backup import DailyBackup, make_backup
from app.services.errors import Busy, Forbidden, NotFound, RuleViolation, TooManyAttempts, Unauthorized
from app.services.plan_sync_scheduler import PlanSyncScheduler
from app.http_guard import BodyLimitMiddleware, SecurityHeadersMiddleware
from app.static_files import mount_spa

logger = logging.getLogger(__name__)

# 画面のビルド成果物。exe では同梱したもの(packaging/genba.spec の frontend_dist)。GENBA_STATIC_DIR で変えられる
_BUNDLED_STATIC = Path(getattr(sys, "_MEIPASS", ".")) / "frontend_dist"
STATIC_DIR = Path(
    os.environ.get("GENBA_STATIC_DIR")
    or (_BUNDLED_STATIC if is_frozen() else Path(__file__).resolve().parents[2] / "frontend" / "dist")
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config = get_config()
    logger.info("基準のフォルダ: %s、DB: %s", config.home or Path.cwd(), config.paths.database)
    # 更新の前のバックアップ(開発指針 10)。DBの構造を変える前に取る
    make_backup(config.paths.database, config.paths.backup_dir, config.backup.keep, "startup")
    engine = init_db(config.paths.database)
    upgrade_to_head(engine)
    daily_backup = DailyBackup(config.paths.database, config.paths.backup_dir, config.backup)
    daily_backup.start()

    scheduler: PlanSyncScheduler | None = None
    if config.paths.legacy_app_dir is None:
        logger.info("paths.legacy_app_dir が未設定のため、計画の同期はしません")
    else:
        scheduler = PlanSyncScheduler(get_sessionmaker(), config.paths.legacy_app_dir, config.sync)
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()
        await daily_backup.stop()
        engine.dispose()


def docs_urls(expose: bool) -> dict[str, str | None]:
    """/docs・/redoc・/openapi.json の場所。本番は None(開かない)。app.openapi() は、開かなくても呼べる。"""
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"} if expose else         {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(title="現場実績入力", version=__version__, lifespan=lifespan, **docs_urls(get_config().server.expose_docs))
# 後に足したものが外側。ヘッダーは 413 にも付けるため、本文の上限より外側に置く
app.add_middleware(BodyLimitMiddleware, max_bytes=get_config().server.max_body_mb * 1024 * 1024)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(health.router)
app.include_router(plans.router)
app.include_router(runs.router)
app.include_router(lines.router)
app.include_router(corrections.router)
app.include_router(admin.router)
app.include_router(admin_masters.router)
app.include_router(admin_reports.router)
app.include_router(admin_actuals.router)


@app.exception_handler(RuleViolation)
def _rule_violation(_request: Request, exc: RuleViolation) -> JSONResponse:
    """業務ルールの違反は 409。detail は画面にそのまま出せる日本語の文。"""
    return JSONResponse(status_code=409, content={"detail": exc.message})


@app.exception_handler(Unauthorized)
def _unauthorized(_request: Request, exc: Unauthorized) -> JSONResponse:
    """管理画面: ログインしていない・切れた・管理者ではない。画面はログイン画面に戻す。"""
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(Forbidden)
def _forbidden(_request: Request, exc: Forbidden) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(TooManyAttempts)
def _too_many(_request: Request, exc: TooManyAttempts) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": exc.message})


@app.exception_handler(NotFound)
def _not_found(_request: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(Busy)
def _busy(_request: Request, exc: Busy) -> JSONResponse:
    """書き込みが重なって記録できなかった。同じ request_id で送り直せば記録される。"""
    return JSONResponse(status_code=503, content={"detail": exc.message})

if STATIC_DIR.exists():
    mount_spa(app, STATIC_DIR, () if get_config().server.expose_docs else ("docs", "redoc", "openapi.json"))
