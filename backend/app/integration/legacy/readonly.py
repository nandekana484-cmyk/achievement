"""既存DBを読み取り専用で開く処理と、既存DBの値の変換。"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

from app.core.clock import JST

_DT_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d")


def open_readonly(db_path: Path, retries: int = 5, wait_sec: float = 0.2) -> sqlite3.Connection:
    """読み取り専用で開く。既存アプリが書き込み中で一時的に読めないときは少し待ってやり直す。"""
    if not db_path.exists():
        raise FileNotFoundError(f"既存DBが見つかりません: {db_path}")
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    last: Exception | None = None
    for _ in range(retries):
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            return conn
        except sqlite3.OperationalError as e:
            last = e
            time.sleep(wait_sec)
    raise last  # type: ignore[misc]


def parse_legacy_datetime(value: str | None) -> datetime | None:
    """既存DBの日時(日本時間)を読む。空なら None、書式が分からなければ ValueError。"""
    if value is None or not str(value).strip():
        return None
    s = str(value).strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=JST)
        except ValueError:
            continue
    raise ValueError(f"日時の形式が不明です: {value!r}")


def to_int(value) -> int | None:  # noqa: ANN001
    """数量(REAL)を整数にする。整数でなければ ValueError。"""
    if value is None or value == "":
        return None
    f = float(value)
    if not f.is_integer():
        raise ValueError(f"数量が整数ではありません: {value!r}")
    return int(f)


def file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, JST)
