"""月次DBの kitting_plan_items から、有効な計画とロットごとの最終書き込み時刻を読む。

詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from app.domain.kitting_no import KittingNoError, parse_kitting_no
from app.domain.normalize import normalize_mounting_line, normalize_setup_file_no
from app.integration.legacy.readonly import open_readonly, parse_legacy_datetime, to_int
from app.integration.legacy.takt import lookup_takt
from app.integration.legacy.types import LegacyPlan, ReadResult, ReadWarning, StaleInfo, TaktKey

# 有効な計画の条件は既存アプリのビュー v_plan_stale と同じ(is_active が NULL は有効、delete_flag=1 は無効)。
# updated_at・created_at は YYYY-MM-DD HH:MM:SS(計画の日時の YYYY/MM/DD とは区切りが違う)
_PLAN_SQL = """
SELECT plan_item_id, kitting_list_no, delete_flag, setup_file_no, lot_no, mounting_line,
       board_name, planned_qty, cumulative_qty_external, order_qty, production_side, status,
       plan_start_datetime, plan_end_datetime, deadline, version, COALESCE(updated_at, created_at) AS written_at
  FROM kitting_plan_items
 WHERE COALESCE(is_active, 1) = 1 AND COALESCE(delete_flag, 0) = 0
"""

# ビューは問い合わせのたびに全体を計算するので、1件ずつ引かず全件を1回で読む(2,500行で約0.05秒)
_STALE_SQL = """
SELECT kitting_list_no, lot_no, is_stale, judge_reason, replacement_kitting_list_no, replacement_count
  FROM v_plan_stale
"""

# 無効な行も含める。updated_at が空の行は created_at で代用する
_LOT_LAST_WRITTEN_SQL = """
SELECT lot_no, MAX(COALESCE(updated_at, created_at)) AS last_written
  FROM kitting_plan_items
 GROUP BY lot_no
"""


def read_active_plans(db_path: Path, takt_master: Mapping[TaktKey, str]) -> ReadResult:
    """有効な計画(is_active=1)と、ロットごとの最終書き込み時刻を読む。形式に合わない行は警告にする。"""
    rows, lot_rows, stale_rows = _read_rows(db_path)
    plans: dict[tuple[str, str], tuple[LegacyPlan, tuple]] = {}
    warnings: list[ReadWarning] = []
    for r in rows:
        kno = (r["kitting_list_no"] or "").strip()
        lot = str(r["lot_no"] or "").strip()  # NULL と '' は同じキー(ビューの lot_no も '' で返る)
        try:
            plan = _plan_from_row(r, kno, lot, takt_master, warnings)
        except (KittingNoError, ValueError, TypeError) as e:
            warnings.append(ReadWarning(r["plan_item_id"], kno or None, lot_no=lot, message=str(e)))
            continue
        _keep_newer(plans, plan, (r["written_at"] or "", r["plan_item_id"]), warnings)
    return ReadResult(
        plans=[p for p, _ in plans.values()], warnings=warnings, lot_last_written=_lot_last_written(lot_rows, warnings),
        stale=_stale_map(stale_rows),
    )


def _keep_newer(
    plans: dict[tuple[str, str], tuple[LegacyPlan, tuple]], plan: LegacyPlan, order: tuple, warnings: list[ReadWarning],
) -> None:
    """同じキーの有効な行が2行以上来たら、更新日時が新しい方(同じなら行番号が大きい方)を採り、警告を出す。

    索引の無い古い月次DBだけで起こりうる。黙って片方を捨てない。
    """
    prev = plans.get(plan.key)
    if prev is None:
        plans[plan.key] = (plan, order)
        return
    old, old_order = prev
    keep, drop = (plan, old) if order >= old_order else (old, plan)
    plans[plan.key] = (keep, max(order, old_order))
    warnings.append(ReadWarning(drop.legacy_plan_item_id, plan.kitting_no, lot_no=plan.lot_no, message=(
        f"同じキッティングNo.・ロットNo.の有効な行が2行以上あります(行 {old.legacy_plan_item_id} と {plan.legacy_plan_item_id})。"
        f"更新日時が新しい行 {keep.legacy_plan_item_id} を採ります")))


def _stale_map(stale_rows: list[sqlite3.Row] | None) -> dict[tuple[str, str], StaleInfo] | None:
    if stale_rows is None:
        return None
    result: dict[tuple[str, str], StaleInfo] = {}
    for r in stale_rows:
        key = ((r["kitting_list_no"] or "").strip(), str(r["lot_no"] or "").strip())
        replacement = (r["replacement_kitting_list_no"] or "").strip() or None
        result[key] = StaleInfo(bool(r["is_stale"]), str(r["judge_reason"] or ""), replacement, int(r["replacement_count"] or 0))
    return result


def _read_rows(db_path: Path) -> tuple[list[sqlite3.Row], list[sqlite3.Row], list[sqlite3.Row] | None]:
    """計画・ロットの最終書き込み時刻・古い計画の判定を、1つの読み取りトランザクションで読み、すぐに閉じる(既存アプリを待たせない)。

    ビューが無い月次DB(既存アプリ 5.0.0 でまだ開いていない)・読めないときは、判定だけ None(計画の読み取りは失敗にしない)。
    """
    conn = open_readonly(db_path)
    try:
        conn.execute("BEGIN")
        rows = conn.execute(_PLAN_SQL).fetchall()
        lot_rows = conn.execute(_LOT_LAST_WRITTEN_SQL).fetchall()
        try:
            stale_rows: list[sqlite3.Row] | None = conn.execute(_STALE_SQL).fetchall()
        except sqlite3.OperationalError:
            stale_rows = None
        conn.execute("COMMIT")
    finally:
        conn.close()
    return rows, lot_rows, stale_rows


def _plan_from_row(
    r: sqlite3.Row, kno: str, lot: str, takt_master: Mapping[TaktKey, str], warnings: list[ReadWarning],
) -> LegacyPlan:
    """1行を LegacyPlan にする。読めない行は例外にする(食い違いだけなら警告を足して採用する)。"""
    item_id = r["plan_item_id"]
    parsed = parse_kitting_no(kno)
    side = _side(r, parsed.run_no, item_id, kno, lot, warnings)
    line = _line(r, parsed.line_code, item_id, kno, lot, warnings)
    file_no = normalize_setup_file_no(r["setup_file_no"]) or normalize_setup_file_no(parsed.file_no)
    planned_qty = to_int(r["planned_qty"])
    if planned_qty is None:
        raise ValueError("数量が空です")
    values = dict(
        cumulative_qty=to_int(r["cumulative_qty_external"]),
        order_qty=to_int(r["order_qty"]),
        planned_start=parse_legacy_datetime(r["plan_start_datetime"]),
        planned_end=parse_legacy_datetime(r["plan_end_datetime"]),
        deadline=parse_legacy_datetime(r["deadline"]),
    )
    # 読めた行だけタクトを探す(読めない行にタクトの警告を重ねない)
    takt_sec = lookup_takt(takt_master, (file_no, line, side), item_id, kno, lot, warnings)
    return LegacyPlan(
        kitting_no=kno, lot_no=lot, file_no=file_no, line_code=line,
        product_name=(r["board_name"] or "").strip(), run_no=side, planned_qty=planned_qty, **values,
        delete_flag=bool(to_int(r["delete_flag"]) or 0), status=r["status"],
        legacy_plan_item_id=item_id, legacy_version=r["version"] or 1, takt_sec=takt_sec,
    )


def _side(r: sqlite3.Row, kno_run: int, item_id: int, kno: str, lot: str, warnings: list[ReadWarning]) -> int:
    """面(production_side)。キッティングNo.の回と食い違えば、警告を出して面を採用する。"""
    side = int(str(r["production_side"]).strip())
    if side not in (1, 2):
        raise ValueError(f"面が1・2以外です: {r['production_side']!r}")
    if side != kno_run:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot,
                                    message=f"面({side})とキッティングNo.の回({kno_run})が食い違っています。面を採用します"))
    return side


def _line(r: sqlite3.Row, kno_line_raw: str, item_id: int, kno: str, lot: str, warnings: list[ReadWarning]) -> str:
    """実装ライン(正規化)。キッティングNo.のラインと食い違えば、警告を出して実装ラインを採用する。"""
    kno_line = normalize_mounting_line(kno_line_raw)
    line = normalize_mounting_line(r["mounting_line"]) or kno_line
    if line != kno_line:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot,
                                    message=f"実装ライン({line})とキッティングNo.のライン({kno_line})が食い違っています。実装ラインを採用します"))
    return line


def _lot_last_written(lot_rows: list[sqlite3.Row], warnings: list[ReadWarning]) -> dict[str, datetime | None]:
    """ロットごとの最終書き込み時刻。前後の空白だけが違うロットNo.は1つにまとめる。"""
    result: dict[str, datetime | None] = {}
    for r in lot_rows:
        lot = str(r["lot_no"] or "").strip()
        try:
            t = parse_legacy_datetime(r["last_written"])
        except ValueError:
            warnings.append(ReadWarning(None, None, lot_no=lot, message=f"ロットの最終書き込み時刻を読めません: {r['last_written']!r}"))
            t = None
        prev = result.get(lot)
        result[lot] = t if prev is None else (prev if t is None else max(prev, t))
    return result
