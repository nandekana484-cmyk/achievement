"""本アプリのDB(SQLite)への接続。

- WALモードで開き、複数端末からの読み取りと書き込みを両立させる
- 外部キー制約を有効にする
- 既存アプリのDBはここでは扱わない(integration/ で読み取り専用に開く)
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.close()

    return engine


_SessionLocal: sessionmaker[Session] | None = None


def init_db(db_path: Path) -> Engine:
    global _SessionLocal
    engine = make_engine(db_path)
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def get_sessionmaker() -> sessionmaker[Session]:
    """API 以外(定期同期など)でセッションを作るときに使う。"""
    if _SessionLocal is None:
        raise RuntimeError("init_db() が呼ばれていません")
    return _SessionLocal


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
