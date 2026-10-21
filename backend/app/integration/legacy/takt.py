"""想定タクト(master.db の production_side_master)の読み取りと、計画への付与。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

from app.domain.normalize import normalize_mounting_line, normalize_setup_file_no
from app.integration.legacy.readonly import open_readonly
from app.integration.legacy.types import ReadWarning, TaktKey

# 正規化すると同じキーになり、値が異なる行があった印
CONFLICT = "\0conflict"


def parse_takt_sec(value) -> float:  # noqa: ANN001
    """takt_time(TEXT。"30"、"55.72" など)を数値にする。読めなければ ValueError。"""
    if value is None or not str(value).strip():
        raise ValueError("空です")
    f = float(str(value).strip())
    if not math.isfinite(f):  # nan は等しさの比較ができず、毎回「変更あり」になってしまう
        raise ValueError(f"数値ではありません: {value!r}")
    return f


def read_takt_master(master_db_path: Path) -> dict[TaktKey, str]:
    """想定タクトを (ファイルNo., 実装ライン, 面) ごとに、正規化したキーで読む。値は文字列のまま。

    正規化すると同じキーになり値が異なる行は、どちらとも決めず CONFLICT にする。
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
        result[key] = CONFLICT if key in result and result[key] != value else value
    return result


def lookup_takt(
    takt_master: Mapping[TaktKey, str], key: TaktKey, item_id: int, kno: str, lot: str,
    warnings: list[ReadWarning],
) -> float | None:
    """計画の想定タクトを探す。マスタに無い・読めないときは None にして警告を足す。"""
    file_no, line, side = key
    where = f"ファイルNo. {file_no}、ライン {line}、面 {side}"
    if key not in takt_master:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"想定タクトがマスタにありません({where})"))
        return None
    raw = takt_master[key]
    if raw is CONFLICT:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot,
                                    message=f"想定タクトのマスタに、正規化すると同じになり値が異なる行があります({where})"))
        return None
    try:
        return parse_takt_sec(raw)
    except ValueError as e:
        warnings.append(ReadWarning(item_id, kno, lot_no=lot, message=f"想定タクトを数値として読めません({where}): {e}"))
        return None
