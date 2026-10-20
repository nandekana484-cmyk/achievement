"""既存アプリのDBから計画を読む(読み取り専用)。

開発指針 0-1: 既存アプリのDBには絶対に書き込まない。このモジュールだけが既存DBを開く。

既存アプリの計画の持ち方(既存アプリ側AIの調査結果, 2026-10-20):
- 計画は月次DBの kitting_plan_items(1行=1計画=1面)
- 計画を変えると、前の行を is_active=0 にして新しい行を INSERT する「版」方式。行は消さない
- 「キッティングNo.+ロットNo.」で有効な行は1件まで(部分ユニークインデックス)
- 内容が同じでも取り込み直すと版が上がる → 変化の判定に version は使えない。内容で比べる
- 想定タクトは計画表になく、master.db の production_side_master.takt_time(TEXT)にある
  (ファイルNo.・実装ライン・面ごと)
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.core.clock import JST
from app.domain.kitting_no import KittingNoError, parse_kitting_no

_DT_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d")


@dataclass(frozen=True)
class LegacyPlan:
    """既存アプリの有効な計画1行を、本アプリで扱う形に直したもの。"""

    kitting_no: str
    lot_no: str
    file_no: str
    line_code: str
    product_name: str
    run_no: int  # 面。1=1回目、2=2回目(production_side)
    planned_qty: int
    cumulative_qty: int | None  # 既存アプリの値を正とする
    order_qty: int | None
    planned_start: datetime | None
    planned_end: datetime | None
    deadline: datetime | None
    delete_flag: bool
    status: str | None
    # 追跡用(既存側の行番号と版)
    legacy_plan_item_id: int
    legacy_version: int

    @property
    def key(self) -> tuple[str, str]:
        """計画の識別キー。既存アプリと同じく「キッティングNo.+ロットNo.」。"""
        return (self.kitting_no, self.lot_no)

    def content(self) -> tuple:
        """変化の判定に使う内容。version や行番号は含めない。"""
        return (
            self.file_no, self.line_code, self.product_name, self.run_no,
            self.planned_qty, self.cumulative_qty, self.order_qty,
            self.planned_start, self.planned_end, self.deadline,
            self.delete_flag, self.status,
        )


@dataclass(frozen=True)
class ReadWarning:
    legacy_plan_item_id: int | None
    kitting_no: str | None
    message: str
    lot_no: str | None = None  # 読めなかった行でも、取れる範囲で入れる

    @property
    def key(self) -> tuple[str, str] | None:
        """警告の行の計画のキー。キッティングNo.が空のときは計画と結びつけられないので None。"""
        if not self.kitting_no or self.lot_no is None:
            return None
        return (self.kitting_no, self.lot_no)


@dataclass(frozen=True)
class ReadResult:
    plans: list[LegacyPlan]
    warnings: list[ReadWarning]


def parse_legacy_datetime(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    s = str(value).strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=JST)
        except ValueError:
            continue
    raise ValueError(f"日時の形式が不明です: {value!r}")


def _to_int(value) -> int | None:  # noqa: ANN001
    if value is None or value == "":
        return None
    f = float(value)
    if not f.is_integer():
        raise ValueError(f"数量が整数ではありません: {value!r}")
    return int(f)


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


_PLAN_SQL = """
SELECT plan_item_id, kitting_list_no, delete_flag, setup_file_no, lot_no, mounting_line,
       board_name, planned_qty, cumulative_qty_external, order_qty, production_side, status,
       plan_start_datetime, plan_end_datetime, deadline, version
  FROM kitting_plan_items
 WHERE is_active = 1
"""


def read_active_plans(db_path: Path) -> ReadResult:
    """有効な計画(is_active=1)をすべて読む。形式に合わない行は取り込まずに警告にする。

    TODO(要確認): 月次DBのファイル名の規則と、月をまたぐ計画の扱い(今は1ファイルだけ読む)
    """
    conn = open_readonly(db_path)
    try:
        rows = conn.execute(_PLAN_SQL).fetchall()
    finally:
        conn.close()

    plans: list[LegacyPlan] = []
    warnings: list[ReadWarning] = []
    for r in rows:
        item_id = r["plan_item_id"]
        kno = (r["kitting_list_no"] or "").strip()
        lot = str(r["lot_no"] or "").strip()
        try:
            parsed = parse_kitting_no(kno)
            side = int(str(r["production_side"]).strip())
            if side not in (1, 2):
                raise ValueError(f"面が1・2以外です: {r['production_side']!r}")
            if side != parsed.run_no:
                warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"面({side})とキッティングNo.の回({parsed.run_no})が食い違っています。面を採用します"))
            line = (r["mounting_line"] or "").strip() or parsed.line_code
            if line != parsed.line_code:
                warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"実装ライン({line})とキッティングNo.のライン({parsed.line_code})が食い違っています。実装ラインを採用します"))
            file_no = (r["setup_file_no"] or "").strip() or parsed.file_no
            planned_qty = _to_int(r["planned_qty"])
            if planned_qty is None:
                raise ValueError("数量が空です")
            plans.append(LegacyPlan(
                kitting_no=kno,
                lot_no=lot,
                file_no=file_no,
                line_code=line,
                product_name=(r["board_name"] or "").strip(),
                run_no=side,
                planned_qty=planned_qty,
                cumulative_qty=_to_int(r["cumulative_qty_external"]),
                order_qty=_to_int(r["order_qty"]),
                planned_start=parse_legacy_datetime(r["plan_start_datetime"]),
                planned_end=parse_legacy_datetime(r["plan_end_datetime"]),
                deadline=parse_legacy_datetime(r["deadline"]),
                # TODO(要確認): delete_flag(計画CSVの「削除」欄)が立った有効な行の意味。今は「取消」として扱う
                delete_flag=bool(_to_int(r["delete_flag"]) or 0),
                # TODO(要確認): status 列の値の種類と意味
                status=r["status"],
                legacy_plan_item_id=item_id,
                legacy_version=r["version"] or 1,
            ))
        except (KittingNoError, ValueError, TypeError) as e:
            warnings.append(ReadWarning(item_id, kno or None, lot_no=lot, message=str(e)))
    return ReadResult(plans=plans, warnings=warnings)


def read_takt_master(master_db_path: Path) -> dict[tuple[str, str, int], str]:
    """想定タクトを (ファイルNo., 実装ライン, 面) ごとに読む。値は既存の文字列のまま返す。

    TODO(要確認): production_side_master の列名と、takt_time の書式(秒か、mm:ss か)
    """
    conn = open_readonly(master_db_path)
    try:
        rows = conn.execute(
            "SELECT setup_file_no, mounting_line, production_side, takt_time FROM production_side_master"
        ).fetchall()
    finally:
        conn.close()
    result: dict[tuple[str, str, int], str] = {}
    for r in rows:
        try:
            side = int(str(r["production_side"]).strip())
        except (TypeError, ValueError):
            continue
        result[(str(r["setup_file_no"]).strip(), str(r["mounting_line"]).strip(), side)] = r["takt_time"]
    return result
