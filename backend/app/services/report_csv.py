"""区間の CSV(管理画面から出す)。1行 = 1つの区間。見出しは日本語、BOM 付きの UTF-8、改行は CRLF(Excel でそのまま開ける)。

詳細: docs/design/reports.md
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Callable

from app.core.clock import JST
from app.services.report_intervals import KIND_LINE_EVENT, IntervalOut

KIND_LABELS = {KIND_LINE_EVENT: "付帯作業"}


def _time(t: dt.datetime | None) -> str:
    return t.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S") if t is not None else ""


def _flag(v: bool) -> str:
    return "○" if v else ""


# (見出し, 値の取り出し)
COLUMNS: list[tuple[str, Callable[[IntervalOut], object]]] = [
    ("稼働日", lambda r: r.workday.isoformat()),
    ("ライン", lambda r: r.line_code),
    ("区分", lambda r: KIND_LABELS.get(r.kind, "工程")),
    ("キッティングNo.", lambda r: r.kitting_no or ""),
    ("ロットNo.", lambda r: r.lot_nos),
    ("ファイルNo.", lambda r: r.file_no or ""),
    ("品名", lambda r: r.product_names),
    ("回", lambda r: r.run_no if r.run_no is not None else ""),
    ("工程または理由", lambda r: r.what),
    ("再開理由", lambda r: r.restart_reason or ""),
    ("設備", lambda r: r.equipment or ""),
    ("理由の記入", lambda r: r.reason_text or ""),
    ("元の開始", lambda r: _time(r.original_start)),
    ("元の終了", lambda r: _time(r.original_end)),
    ("開始(この稼働日)", lambda r: _time(r.start)),
    ("終了(この稼働日)", lambda r: _time(r.end)),
    ("時間(分)", lambda r: f"{r.minutes:.1f}"),
    ("作業中", lambda r: _flag(r.open)),
    ("生産数", lambda r: r.produced_qty if r.produced_qty is not None else ""),
    ("開始した人", lambda r: r.started_by),
    ("終了した人", lambda r: r.ended_by or ""),
    ("後から追加", lambda r: _flag(r.added_later)),
    ("訂正あり", lambda r: _flag(r.corrected)),
]

HEADERS = [h for h, _ in COLUMNS]

# 人が入れた文字の列。Excel で式として動かないよう、先頭が危ない文字なら ' を付ける(S-03。詳細: docs/design/security.md)。
# キッティングNo.・ロットNo.・ファイルNo. などの識別の列は、取り込み側が完全一致で使うので変えない
FREE_TEXT_HEADERS = {"品名", "工程または理由", "再開理由", "設備", "理由の記入", "開始した人", "終了した人"}
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    return "'" + value if value.startswith(_FORMULA_STARTS) else value


def intervals_csv(rows: list[IntervalOut]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(HEADERS)
    for r in rows:
        w.writerow([safe_cell(get(r)) if h in FREE_TEXT_HEADERS else get(r) for h, get in COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


def csv_filename(day_from: dt.date, day_to: dt.date, line_code: str | None) -> str:
    """例: intervals_2026-10-01_2026-10-31_S.csv(ラインを省略したら all)。"""
    return f"intervals_{day_from.isoformat()}_{day_to.isoformat()}_{line_code or 'all'}.csv"
