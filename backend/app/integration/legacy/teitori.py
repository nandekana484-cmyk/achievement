"""丁取り(master.db のビュー v_board_teitori)の読み取り。読み取り専用。

詳細: docs/design/metrics.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.normalize import normalize_mounting_line, normalize_setup_file_no
from app.integration.legacy.readonly import open_readonly

VIEW_NAME = "v_board_teitori"
STATUS_OK = "ok"
STATUS_TEITORI_INVALID = "teitori_invalid"


@dataclass(frozen=True)
class LegacyTeitori:
    setup_file_no: str  # 正規化した値
    mounting_line: str  # 正規化した値
    part_no: str | None
    teitori: int | None  # status が ok のときだけ、1以上の整数
    status: str
    fetched_at: str | None


def _valid_teitori(value) -> int | None:  # noqa: ANN001
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if value >= 1 and value == int(value) else None


def read_teitori(master_db_path: Path) -> list[LegacyTeitori] | None:
    """ビューの全行を1回で読む。ビューが無い master.db(既存アプリが 4.1.0 より前)なら None。

    キーは既存アプリと同じ規則で正規化し直す(正規化済みの値には何も起きない)。
    status が ok でも丁取り数が1以上の整数でなければ teitori_invalid にし、ok 以外では丁取り数を使わない。
    """
    conn = open_readonly(master_db_path)
    try:
        found = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = ?", (VIEW_NAME,)).fetchone()
        if found is None:
            return None
        rows = conn.execute(
            f"SELECT setup_file_no, mounting_line, part_no, teitori, status, fetched_at FROM {VIEW_NAME}"
        ).fetchall()
    finally:
        conn.close()
    result: dict[tuple[str, str], LegacyTeitori] = {}
    for r in rows:
        file_no, line = normalize_setup_file_no(r["setup_file_no"]), normalize_mounting_line(r["mounting_line"])
        if not file_no or not line:
            continue
        status = str(r["status"] or "").strip() or "unknown"
        teitori = _valid_teitori(r["teitori"]) if status == STATUS_OK else None
        if status == STATUS_OK and teitori is None:
            status = STATUS_TEITORI_INVALID
        result[(file_no, line)] = LegacyTeitori(
            file_no, line, r["part_no"], teitori, status, str(r["fetched_at"]) if r["fetched_at"] is not None else None,
        )
    return list(result.values())
