"""本アプリのDB(SQLite、WAL)への接続と、書き込みのトランザクション(write_transaction)。

詳細: docs/design/db-writes.md
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# 書き込みのロックを待つ時間(ミリ秒)。テストでは短くして、ロックの取り合いを起こす
BUSY_TIMEOUT_MS = 10_000

# 実行オプション。これが付いた接続のトランザクションは BEGIN IMMEDIATE で始める
_IMMEDIATE = "genba_begin_immediate"

# 同じプロセス内の書き込みを1つずつ行う(1プロセス前提。開発指針 0-7)
write_lock = threading.RLock()


class Base(DeclarativeBase):
    pass


def make_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": BUSY_TIMEOUT_MS / 1000},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # noqa: ANN001
        # pysqlite 自身がトランザクションを始めないようにする(開始は下の begin イベントで行う)
        dbapi_conn.isolation_level = None
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute(f"PRAGMA busy_timeout={int(BUSY_TIMEOUT_MS)}")
        cur.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn):  # noqa: ANN001
        conn.exec_driver_sql("BEGIN IMMEDIATE" if conn.get_execution_options().get(_IMMEDIATE) else "BEGIN")

    return engine


@contextmanager
def write_transaction(session: Session) -> Iterator[None]:
    """書き込む処理を囲む。プロセス内のロックを取り、BEGIN IMMEDIATE で始める(中でコミットまで行う)。"""
    with write_lock:
        if session.in_transaction():  # 古い読み取りにもとづいて書かないよう、いったん終える
            session.commit()
        session.connection(execution_options={_IMMEDIATE: True})
        yield


def is_busy_error(exc: BaseException) -> bool:
    """SQLite の database is locked / busy か。"""
    orig = exc.orig if isinstance(exc, OperationalError) else exc
    if not isinstance(orig, sqlite3.OperationalError):
        return False
    code = getattr(orig, "sqlite_errorcode", None)
    if code is not None and (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return True
    message = str(orig).lower()
    return "database is locked" in message or "database is busy" in message


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
