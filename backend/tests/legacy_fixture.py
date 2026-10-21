"""テスト用に、既存アプリと同じフォルダ構成・同じ構造のDBを作る(列は既存側AIの調査結果のとおり)。

<既存アプリのフォルダ>\\db\\<フォルダ名>\\inventory.db  月次DB
<既存アプリのフォルダ>\\db\\inventory.db               既定DB(未選択)
<既存アプリのフォルダ>\\db\\master.db                  共通マスタ

created_at / updated_at は、既存アプリと同じく "YYYY-MM-DD HH:MM:SS"(日本時間)で入れる。
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from datetime import datetime
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

MASTER_DDL = """
CREATE TABLE production_side_master (
  row_key TEXT PRIMARY KEY,
  setup_file_no TEXT NOT NULL,
  mounting_line TEXT NOT NULL,
  production_side TEXT NOT NULL,
  bond_flag TEXT, common_parts_group TEXT, line_priority TEXT,
  takt_time TEXT,
  imported_at TEXT,
  UNIQUE(setup_file_no, mounting_line, production_side)
);
CREATE TABLE workers (
  worker_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT DEFAULT 'operator',
  is_active INTEGER DEFAULT 1
);
"""

# 想定タクトのマスタ (setup_file_no, mounting_line, production_side) → takt_time。値は既存アプリと同じく文字列
DEFAULT_TAKT: dict[tuple[str, str, str], str] = {
    ("0722", "S", "1"): "30",
    ("0722", "S", "2"): "55.72",
    ("0722", "T", "1"): "40",
}

# 読み取りの単体テスト用(read_takt_master が返す形: 正規化したキー → 文字列)
TAKT = {(f, line, int(side)): v for (f, line, side), v in DEFAULT_TAKT.items()}

DEFAULT_AT = "2026-10-20 10:00:00"


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    """コミットして、接続も必ず閉じる(sqlite3 の with はコミットするだけで閉じないため)。"""
    with closing(sqlite3.connect(path)) as c, c:
        yield c


def make_plan_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as c:
        c.executescript(PLAN_DDL)


def make_master_db(path: Path, takt: Mapping[tuple[str, str, str], str | None] = DEFAULT_TAKT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as c:
        c.executescript(MASTER_DDL)
        for (file_no, line, side), value in takt.items():
            c.execute(
                "INSERT INTO production_side_master (row_key, setup_file_no, mounting_line, production_side, takt_time) VALUES (?,?,?,?,?)",
                (f"{file_no}|{line}|{side}", file_no, line, side, value),
            )


def put_worker(master: Path, worker_id: str, name: str, role: str = "operator", active: bool = True) -> None:
    """既存アプリの作業者を足す、または変える(既存アプリと同じく行は消さない)。"""
    with _connect(master) as c:
        c.execute(
            "INSERT INTO workers (worker_id, name, role, is_active) VALUES (?,?,?,?) "
            "ON CONFLICT(worker_id) DO UPDATE SET name=excluded.name, role=excluded.role, is_active=excluded.is_active",
            (worker_id, name, role, int(active)),
        )


def delete_worker(master: Path, worker_id: str) -> None:
    """既存アプリから作業者が見えなくなった場合(既存アプリは消さないが、DBを入れ替えたときなど)。"""
    with _connect(master) as c:
        c.execute("DELETE FROM workers WHERE worker_id = ?", (worker_id,))


def drop_workers_table(master: Path) -> None:
    with _connect(master) as c:
        c.execute("DROP TABLE workers")


def drop_takt_table(master: Path) -> None:
    """想定タクトの表が無い master.db(計画の同期はエラーになる)。"""
    with _connect(master) as c:
        c.execute("DROP TABLE production_side_master")


def make_legacy_app(root: Path, takt: Mapping[tuple[str, str, str], str | None] = DEFAULT_TAKT) -> Path:
    """既存アプリのフォルダを作る(db フォルダと master.db だけ。月次DBは add_monthly_db で足す)。"""
    make_master_db(root / "db" / "master.db", takt)
    return root


def add_monthly_db(app_dir: Path, name: str) -> Path:
    path = app_dir / "db" / name / "inventory.db"
    make_plan_db(path)
    return path


def insert_plan(path: Path, *, kitting_no: str, lot_no: str = "L001", side: str = "1",
                qty: float = 300, line: str = "S", file_no: str = "0722",
                start: str = "2026/10/21 09:00:00", end: str = "2026/10/21 12:00:00",
                delete_flag: int = 0, board: str = "基板A", at: str = DEFAULT_AT) -> int:
    """「版」方式で計画を入れる: 同じキーの有効な行があれば無効にして新しい版を足す。

    既存アプリと同じく、古い行は is_active=0 と updated_at だけを更新し、新しい行は INSERT 時刻(at)にする。
    """
    with _connect(path) as c:
        prev = c.execute(
            "SELECT plan_item_id, version FROM kitting_plan_items WHERE kitting_list_no=? AND lot_no=? AND is_active=1",
            (kitting_no, lot_no),
        ).fetchone()
        if prev:
            c.execute("UPDATE kitting_plan_items SET is_active=0, updated_at=? WHERE plan_item_id=?", (at, prev[0]))
        cur = c.execute(
            """INSERT INTO kitting_plan_items (kitting_list_no, delete_flag, setup_file_no, lot_no, mounting_line,
                 board_name, planned_qty, cumulative_qty_external, order_qty, production_side, status,
                 plan_start_datetime, plan_end_datetime, deadline, version, is_active, previous_plan_item_id,
                 created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
            (kitting_no, delete_flag, file_no, lot_no, line, board, qty, 0, 1000, side, None,
             start, end, "2026/10/31", (prev[1] + 1) if prev else 1, prev[0] if prev else None, at, at),
        )
        return cur.lastrowid


def deactivate(path: Path, kitting_no: str, lot_no: str = "L001", at: str = DEFAULT_AT) -> None:
    with _connect(path) as c:
        c.execute(
            "UPDATE kitting_plan_items SET is_active=0, updated_at=? WHERE kitting_list_no=? AND lot_no=? AND is_active=1",
            (at, kitting_no, lot_no),
        )


def soft_delete_lot(path: Path, lot_no: str, at: str) -> None:
    """既存アプリの「削除(ソフト)」: 有効な行を is_active=0 にして updated_at を更新する。"""
    with _connect(path) as c:
        c.execute("UPDATE kitting_plan_items SET is_active=0, updated_at=? WHERE lot_no=? AND is_active=1", (at, lot_no))


def copy_lot(src: Path, dst: Path, lot_no: str, at: str) -> None:
    """既存アプリの前月からの引き継ぎ: ロットの有効な行を、コピーした時刻で別のDBに写す(元の時刻は写さない)。"""
    cols = ("kitting_list_no, delete_flag, setup_file_no, lot_no, mounting_line, board_name, planned_qty, "
            "cumulative_qty_external, order_qty, production_side, status, plan_start_datetime, plan_end_datetime, deadline")
    with _connect(src) as c:
        rows = c.execute(f"SELECT {cols} FROM kitting_plan_items WHERE lot_no=? AND is_active=1", (lot_no,)).fetchall()
    with _connect(dst) as c:
        for r in rows:
            c.execute(
                f"INSERT INTO kitting_plan_items ({cols}, version, is_active, created_at, updated_at) "
                f"VALUES ({','.join('?' * 14)}, 1, 1, ?, ?)",
                (*r, at, at),
            )


def set_mtime(path: Path, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(path, (ts, ts))
