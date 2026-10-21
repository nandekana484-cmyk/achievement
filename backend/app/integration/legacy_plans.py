"""既存アプリのDBから計画を読む(読み取り専用)。

開発指針 0-1: 既存アプリのDBには絶対に書き込まない。このモジュールだけが既存DBを開く。

既存アプリの計画の持ち方(既存アプリ側AIの調査結果, 2026-10-20 / 2026-10-21):
- 計画は月次DBの kitting_plan_items(1行=1計画=1面)
- 計画を変えると、前の行を is_active=0 にして新しい行を INSERT する「版」方式。行は消さない
- 「キッティングNo.+ロットNo.」で有効な行は1件まで(部分ユニークインデックス)
- 内容が同じでも取り込み直すと版が上がる → 変化の判定に version は使えない。内容で比べる
- 想定タクトは計画表になく、master.db の production_side_master.takt_time(TEXT。小数の数値)にある
  (ファイルNo.・実装ライン・面ごと)

フォルダの構成:
- <既存アプリのフォルダ>\\db\\<フォルダ名>\\inventory.db が月次DB(フォルダ名は自由)。すべて読む
- <既存アプリのフォルダ>\\db\\inventory.db は「未選択」を表す既定DB。読まない
- <既存アプリのフォルダ>\\db\\master.db は共通マスタ
- どのDBも journal_mode=delete。読み取り中は既存アプリの書き込みを待たせるので、1つのDBの読み取りは短く終える
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from app.core.clock import JST
from app.domain.kitting_no import KittingNoError, parse_kitting_no
from app.domain.normalize import normalize_mounting_line, normalize_setup_file_no

_DT_FORMATS = ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d")

MONTHLY_DB_NAME = "inventory.db"
MASTER_DB_NAME = "master.db"

TaktKey = tuple[str, str, int]  # (正規化したファイルNo., 正規化した実装ライン, 面)
_CONFLICT = "\0conflict"  # 想定タクトのマスタで、正規化すると同じキーになり値が異なる


@dataclass(frozen=True)
class LegacyPlan:
    """既存アプリの有効な計画1行を、本アプリで扱う形に直したもの。"""

    kitting_no: str
    lot_no: str
    file_no: str  # 既存アプリと同じく正規化した値
    line_code: str  # 既存アプリと同じく正規化した値
    product_name: str
    run_no: int  # 面。1=1回目、2=2回目(production_side)
    planned_qty: int
    cumulative_qty: int | None  # 既存アプリの値を正とする
    order_qty: int | None
    planned_start: datetime | None
    planned_end: datetime | None
    deadline: datetime | None
    delete_flag: bool  # 保存するだけ。業務上の意味が分からないため、取消の判定には使わない
    status: str | None
    # 追跡用(既存側の行番号と版)
    legacy_plan_item_id: int
    legacy_version: int
    # TODO(要確認): 想定タクトの単位(今は「1枚あたりの秒」と仮定)
    takt_sec: float | None = None

    @property
    def key(self) -> tuple[str, str]:
        """計画の識別キー。既存アプリと同じく「キッティングNo.+ロットNo.」。"""
        return (self.kitting_no, self.lot_no)

    def content(self) -> tuple:
        """変化の判定に使う内容。version、行番号、delete_flag は含めない。"""
        return (
            self.file_no, self.line_code, self.product_name, self.run_no,
            self.planned_qty, self.cumulative_qty, self.order_qty,
            self.planned_start, self.planned_end, self.deadline,
            self.status, self.takt_sec,
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
    # ロットごとの最終書き込み時刻(無効な行も含めた MAX(updated_at))。時刻が読めないロットは None
    lot_last_written: dict[str, datetime | None] = field(default_factory=dict)


@dataclass(frozen=True)
class MonthlyDbRead:
    """月次DB 1つ分の読み取り結果。"""

    name: str  # DBのフォルダ名
    path: Path
    file_mtime: datetime  # DBファイルの更新日時
    result: ReadResult


@dataclass(frozen=True)
class SkippedDb:
    name: str
    path: Path
    file_mtime: datetime
    reason: str


@dataclass(frozen=True)
class LegacySourceRead:
    """既存アプリのすべての月次DBの読み取り結果。"""

    dbs: list[MonthlyDbRead]
    skipped: list[SkippedDb]


class LegacySourceError(Exception):
    """既存アプリのDBを読めなかった(1つでも読めなければ、同期は何も反映しない)。"""


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


def parse_takt_sec(value) -> float:  # noqa: ANN001
    """production_side_master.takt_time(TEXT。"30"、"55.72" など)を数値にする。読めなければ ValueError。"""
    if value is None or not str(value).strip():
        raise ValueError("空です")
    f = float(str(value).strip())
    if not math.isfinite(f):  # nan は等しさの比較ができず、毎回「変更あり」になるため受け付けない
        raise ValueError(f"数値ではありません: {value!r}")
    return f


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

# 無効な行も含めて、ロットごとの最終書き込み時刻。updated_at が空の行は created_at で代用する
_LOT_LAST_WRITTEN_SQL = """
SELECT lot_no, MAX(COALESCE(updated_at, created_at)) AS last_written
  FROM kitting_plan_items
 GROUP BY lot_no
"""


def read_active_plans(db_path: Path, takt_master: Mapping[TaktKey, str]) -> ReadResult:
    """月次DBから、有効な計画(is_active=1)と、ロットごとの最終書き込み時刻を読む。

    形式に合わない行は取り込まずに警告にする。2つの読み取りは1つの読み取りトランザクションで行い、
    すぐに接続を閉じる(既存アプリの書き込みを待たせないため)。
    """
    conn = open_readonly(db_path)
    try:
        conn.execute("BEGIN")
        rows = conn.execute(_PLAN_SQL).fetchall()
        lot_rows = conn.execute(_LOT_LAST_WRITTEN_SQL).fetchall()
        conn.execute("COMMIT")
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
            kno_line = normalize_mounting_line(parsed.line_code)
            line = normalize_mounting_line(r["mounting_line"]) or kno_line
            if line != kno_line:
                warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"実装ライン({line})とキッティングNo.のライン({kno_line})が食い違っています。実装ラインを採用します"))
            file_no = normalize_setup_file_no(r["setup_file_no"]) or normalize_setup_file_no(parsed.file_no)
            planned_qty = _to_int(r["planned_qty"])
            if planned_qty is None:
                raise ValueError("数量が空です")
            cumulative_qty = _to_int(r["cumulative_qty_external"])
            order_qty = _to_int(r["order_qty"])
            planned_start = parse_legacy_datetime(r["plan_start_datetime"])
            planned_end = parse_legacy_datetime(r["plan_end_datetime"])
            deadline = parse_legacy_datetime(r["deadline"])
            # 読めた行だけ、想定タクトを探す(読めない行にタクトの警告を重ねない)
            takt_sec = _lookup_takt(takt_master, (file_no, line, side), item_id, kno, lot, warnings)
            plans.append(LegacyPlan(
                kitting_no=kno,
                lot_no=lot,
                file_no=file_no,
                line_code=line,
                product_name=(r["board_name"] or "").strip(),
                run_no=side,
                planned_qty=planned_qty,
                cumulative_qty=cumulative_qty,
                order_qty=order_qty,
                planned_start=planned_start,
                planned_end=planned_end,
                deadline=deadline,
                # 削除フラグは考慮しない(業務上の意味が分からず、実データでもすべて0のため)。保存だけする
                delete_flag=bool(_to_int(r["delete_flag"]) or 0),
                # status は保存するだけ(本アプリの判定には使わない)
                status=r["status"],
                legacy_plan_item_id=item_id,
                legacy_version=r["version"] or 1,
                takt_sec=takt_sec,
            ))
        except (KittingNoError, ValueError, TypeError) as e:
            warnings.append(ReadWarning(item_id, kno or None, lot_no=lot, message=str(e)))

    lot_last_written: dict[str, datetime | None] = {}
    for r in lot_rows:
        lot = str(r["lot_no"] or "").strip()
        try:
            t = parse_legacy_datetime(r["last_written"])
        except ValueError:
            warnings.append(ReadWarning(None, None, lot_no=lot, message=f"ロットの最終書き込み時刻を読めません: {r['last_written']!r}"))
            t = None
        prev = lot_last_written.get(lot)
        # 前後の空白だけが違うロットNo.は同じロットとしてまとめる
        lot_last_written[lot] = t if prev is None else (prev if t is None else max(prev, t))
    return ReadResult(plans=plans, warnings=warnings, lot_last_written=lot_last_written)


def _lookup_takt(
    takt_master: Mapping[TaktKey, str], key: TaktKey, item_id: int, kno: str, lot: str,
    warnings: list[ReadWarning],
) -> float | None:
    file_no, line, side = key
    if key not in takt_master:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"想定タクトがマスタにありません(ファイルNo. {file_no}、ライン {line}、面 {side})"))
        return None
    raw = takt_master[key]
    if raw is _CONFLICT:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"想定タクトのマスタに、正規化すると同じになり値が異なる行があります(ファイルNo. {file_no}、ライン {line}、面 {side})"))
        return None
    try:
        return parse_takt_sec(raw)
    except ValueError as e:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"想定タクトを数値として読めません(ファイルNo. {file_no}、ライン {line}、面 {side}): {e}"))
        return None


def read_takt_master(master_db_path: Path) -> dict[TaktKey, str]:
    """想定タクトを (ファイルNo., 実装ライン, 面) ごとに読む。キーは既存アプリと同じく正規化する。

    値は既存の文字列のまま返す(数値への変換は計画ごとに行い、読めなければ警告にする)。
    正規化すると同じキーになり値が異なる行があるときは、どちらとも決めず _CONFLICT にする(計画ごとに警告)。
    """
    conn = open_readonly(master_db_path)
    try:
        rows = conn.execute(
            "SELECT setup_file_no, mounting_line, production_side, takt_time FROM production_side_master"
        ).fetchall()
    finally:
        conn.close()
    result: dict[TaktKey, str] = {}
    for r in rows:
        try:
            side = int(str(r["production_side"]).strip())
        except (TypeError, ValueError):
            continue
        key = (normalize_setup_file_no(r["setup_file_no"]), normalize_mounting_line(r["mounting_line"]), side)
        value = r["takt_time"]
        if key in result and result[key] != value:
            result[key] = _CONFLICT
        else:
            result[key] = value
    return result


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, JST)


def find_monthly_dbs(legacy_app_dir: Path, max_age_days: int, now: datetime) -> tuple[list[tuple[str, Path, datetime]], list[SkippedDb]]:
    """<既存アプリのフォルダ>\\db の直下のフォルダにある inventory.db を探す。

    db\\inventory.db(既定DB)は読まない。ファイルの更新日時が max_age_days より古いDBは読まない。
    """
    db_dir = legacy_app_dir / "db"
    if not db_dir.is_dir():
        raise FileNotFoundError(f"既存アプリの db フォルダが見つかりません: {db_dir}")
    limit = now - timedelta(days=max_age_days)
    found: list[tuple[str, Path, datetime]] = []
    skipped: list[SkippedDb] = []
    for folder in sorted(p for p in db_dir.iterdir() if p.is_dir()):
        path = folder / MONTHLY_DB_NAME
        if not path.is_file():
            continue
        mtime = _file_mtime(path)
        if mtime < limit:
            skipped.append(SkippedDb(folder.name, path, mtime, f"更新日時が{max_age_days}日より前"))
            continue
        found.append((folder.name, path, mtime))
    return found, skipped


def read_legacy_source(legacy_app_dir: Path, max_age_days: int, now: datetime) -> LegacySourceRead:
    """master.db と、読む対象のすべての月次DBを読む。DBごとに接続を開いて閉じる。

    1つでも読めないDBがあれば LegacySourceError にする(どのDBの計画が正か決められないため)。
    警告には、どのDBの行かが分かるようにフォルダ名を付ける。
    """
    master = legacy_app_dir / "db" / MASTER_DB_NAME
    try:
        takt_master = read_takt_master(master)
    except (OSError, sqlite3.Error) as e:
        raise LegacySourceError(f"master.db を読めません({master}): {type(e).__name__}: {e}") from e

    try:
        found, skipped = find_monthly_dbs(legacy_app_dir, max_age_days, now)
    except OSError as e:
        raise LegacySourceError(f"{type(e).__name__}: {e}") from e
    if not found:
        raise LegacySourceError(f"読む月次DBがありません({legacy_app_dir / 'db'}。{max_age_days}日以内に更新された <フォルダ>\\{MONTHLY_DB_NAME} が対象)")

    dbs: list[MonthlyDbRead] = []
    for name, path, mtime in found:
        try:
            result = read_active_plans(path, takt_master)
        except (OSError, sqlite3.Error) as e:
            raise LegacySourceError(f"月次DB「{name}」を読めません({path}): {type(e).__name__}: {e}") from e
        result = replace(result, warnings=[replace(w, message=f"[{name}] {w.message}") for w in result.warnings])
        dbs.append(MonthlyDbRead(name=name, path=path, file_mtime=mtime, result=result))
    return LegacySourceRead(dbs=dbs, skipped=skipped)
