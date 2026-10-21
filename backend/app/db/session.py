"""本アプリのDB(SQLite)への接続。

- WALモードで開き、複数端末からの読み取りと書き込みを両立させる
- 外部キー制約を有効にする
- 既存アプリのDBはここでは扱わない(integration/ で読み取り専用に開く)

書き込みの衝突を防ぐ(開発指針 9):
- SQLite は、古い読み取りにもとづく書き込みを拒否する(busy_timeout があっても即座に database is locked になる)。
  そこで、本アプリのDBに書き込む処理は write_transaction() の中で行い、処理の最初に書き込みのロックを取る
  (BEGIN IMMEDIATE)。あわせて、同じプロセス内の書き込みは1つのロックで1つずつ行う
- トランザクションの開始は、SQLAlchemy が pysqlite 向けに示している方法で制御する
  (pysqlite 自身の BEGIN を止め、begin イベントで BEGIN / BEGIN IMMEDIATE を出す)
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

# 本アプリのDBへの書き込み(ボタン操作、計画の同期、開発用コマンド)を1つずつ行うためのロック。
# 1プロセスで動かす前提(開発指針 0-7)。同じスレッドの入れ子は許す
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
    """本アプリのDBに書き込む処理を囲む。プロセス内のロックを取り、トランザクションを BEGIN IMMEDIATE で始める。

    中でコミットまで行うこと。セッションがすでにトランザクションの途中(読み取りなど)なら、
    古い読み取りにもとづいて書かないよう、いったん終えてから始め直す。
    """
    with write_lock:
        if session.in_transaction():
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
