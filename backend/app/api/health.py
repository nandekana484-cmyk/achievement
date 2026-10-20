"""稼働確認(更新後に担当者がブラウザで開いて確かめる)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.clock import now
from app.db.session import get_session

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    journal_mode = session.execute(text("PRAGMA journal_mode")).scalar_one()
    return {
        "status": "ok",
        "version": __version__,
        "server_time": now().isoformat(),
        "db_journal_mode": journal_mode,
    }
