"""テスト用に、既存アプリと同じ構造の計画DBを作る(列は既存側AIの調査結果のとおり)。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

PLAN_DDL = """
CREATE TABLE kitting_plan_items (
  plan_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_batch_id INTEGER,
  kitting_list_no TEXT NOT NULL,
  delete_flag INTEGER,
  setup_file_no TEXT, lot_no TEXT, mounting_line TEXT, board_name TEXT,
  planned_qty REAL, cumulative_qty_external REAL, order_qty REAL,
  production_side TEXT, status TEXT,
  plan_start_datetime TEXT, plan_end_datetime TEXT, deadline TEXT,
  actual_start_datetime TEXT, actual_end_datetime TEXT,
  created_at TEXT, updated_at TEXT,
  version INTEGER, is_active INTEGER, previous_plan_item_id INTEGER, created_by TEXT
);
CREATE UNIQUE INDEX ux_active ON kitting_plan_items(kitting_list_no, lot_no) WHERE is_active = 1;
"""


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    """コミットして、接続も必ず閉じる(sqlite3 の with はコミットするだけで閉じないため)。"""
    with closing(sqlite3.connect(path)) as c, c:
        yield c


def make_plan_db(path: Path) -> None:
    with _connect(path) as c:
        c.executescript(PLAN_DDL)


def insert_plan(path: Path, *, kitting_no: str, lot_no: str = "L001", side: str = "1",
                qty: float = 300, line: str = "S", file_no: str = "0722",
                start: str = "2026/10/21 09:00:00", end: str = "2026/10/21 12:00:00",
                delete_flag: int = 0, board: str = "基板A") -> int:
    """「版」方式で計画を入れる: 同じキーの有効な行があれば無効にして新しい版を足す。"""
    with _connect(path) as c:
        prev = c.execute(
            "SELECT plan_item_id, version FROM kitting_plan_items WHERE kitting_list_no=? AND lot_no=? AND is_active=1",
            (kitting_no, lot_no),
        ).fetchone()
        if prev:
            c.execute("UPDATE kitting_plan_items SET is_active=0 WHERE plan_item_id=?", (prev[0],))
        cur = c.execute(
            """INSERT INTO kitting_plan_items (kitting_list_no, delete_flag, setup_file_no, lot_no, mounting_line,
                 board_name, planned_qty, cumulative_qty_external, order_qty, production_side, status,
                 plan_start_datetime, plan_end_datetime, deadline, version, is_active, previous_plan_item_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
            (kitting_no, delete_flag, file_no, lot_no, line, board, qty, 0, 1000, side, None,
             start, end, "2026/10/31", (prev[1] + 1) if prev else 1, prev[0] if prev else None),
        )
        return cur.lastrowid


def deactivate(path: Path, kitting_no: str, lot_no: str = "L001") -> None:
    with _connect(path) as c:
        c.execute("UPDATE kitting_plan_items SET is_active=0 WHERE kitting_list_no=? AND lot_no=?", (kitting_no, lot_no))
