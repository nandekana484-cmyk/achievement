"""管理表の内容の取り込み(AD-28): 1つのシート(= 1つのファイルNo.)を読んで、管理No と工程の行にする。DBには触れない。

位置は固定でなく、見出しの文字(「管理No」「セットアップファイル」「NO」「工程名」「作業要領」「ライン名」「組立工程へ」)を探して決める。
見出しの前後の空白(全角を含む)と、全角・半角・大文字小文字の違いは無視する。読み方の詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.services.control_sheet_book import SheetData
from app.services.control_sheets import MAX_ROWS, ControlRow

FILE_NO_PATTERN = re.compile(r"^[A-Z0-9]{4}$")  # 既存アプリの setup_file_no の形(4文字の英大文字と数字)
NAME_MAX, PROCEDURE_MAX = 100, 2000  # ControlRow の上限
KINDS = {"社内": "internal", "社外": "external"}
PORTUGUESE_KINDS = {"INTERNO", "EXTERNO"}


class SheetError(Exception):
    """このシートは読めない(理由は画面にそのまま出す)。"""


class SheetSkipped(Exception):
    """このシートは飛ばす(ファイルNo.のシートではない)。"""


@dataclass(frozen=True)
class ParsedSheet:
    file_no: str
    manager_no: str
    rows: list[ControlRow]


def fold(text: str) -> str:
    """見出しの比べ方: 全角を半角に(№ は No)、空白(全角を含む)を除き、英字は大文字にする。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).upper()


def normalize_file_no(raw: str) -> str:
    """ファイルNo.の形にする: 前後の空白を除き、全角を半角に、英字を大文字に。数字だけなら 0 で埋めて4桁(722 → 0722)。"""
    value = fold(raw)
    return value.zfill(4) if value.isdigit() else value


def file_no_of_sheet(name: str) -> str:
    """シート名のファイルNo.。ファイルNo.の形でなければ SheetSkipped(「Sheet1」など)。"""
    key = normalize_file_no(name)
    if not FILE_NO_PATTERN.match(key):
        raise SheetSkipped("シート名がファイルNo.の形(4文字の英大文字と数字)ではないため飛ばしました")
    return key


@dataclass(frozen=True)
class Layout:
    header_row: int
    no_col: int
    name_col: int
    proc_col: int
    line_col: int
    manager_cell: tuple[int, int]  # 管理No の値のセル(見出しの1つ下)
    file_cell: tuple[int, int]  # セットアップファイルNo. の値のセル(見出しの1つ下)
    end_row: int  # 「組立工程へ」の行(工程の行はこの手前まで)


def _find(sheet: SheetData, rows: range, test) -> tuple[int, int] | None:  # noqa: ANN001
    for r in rows:
        for c in range(1, sheet.max_col + 1):
            if test(fold(sheet.text(r, c))):
                return r, c
    return None


def _table_header(sheet: SheetData) -> tuple[int, dict[str, int]]:
    """見出しの行(NO・工程名・作業要領・ライン名が同じ行にある最初の行)と、その列。"""
    wanted = {"no": lambda t: t == "NO", "name": lambda t: "工程名" in t, "proc": lambda t: "作業要領" in t, "line": lambda t: "ライン名" in t}
    seen: set[str] = set()
    for r in range(1, sheet.max_row + 1):
        cols: dict[str, int] = {}
        for c in range(1, sheet.max_col + 1):
            t = fold(sheet.text(r, c))
            for key, test in wanted.items():
                if key not in cols and t and test(t):
                    cols[key] = c
        seen.update(cols)
        if len(cols) == len(wanted):
            return r, cols
    labels = {"no": "NO", "name": "工程名", "proc": "作業要領", "line": "ライン名"}
    missing = [labels[k] for k in wanted if k not in seen]
    raise SheetError("見出し「" + "」「".join(missing) + "」が見つかりません" if missing else "見出し(NO・工程名・作業要領・ライン名)が同じ行に見つかりません")


def find_layout(sheet: SheetData) -> Layout:
    header_row, cols = _table_header(sheet)
    above = range(1, header_row)
    manager = _find(sheet, above, lambda t: t.startswith("管理NO"))
    if manager is None:
        raise SheetError("見出し「管理No」が見つかりません")
    file_head = _find(sheet, above, lambda t: "セットアップファイル" in t)
    if file_head is None:
        raise SheetError("見出し「セットアップファイル」が見つかりません")
    end = next((r for r in range(header_row + 1, sheet.max_row + 1) if "組立工程へ" in fold(sheet.text(r, cols["proc"]))), None)
    if end is None:
        raise SheetError("「組立工程へ」の行が見つかりません")
    return Layout(header_row, cols["no"], cols["name"], cols["proc"], cols["line"], (manager[0] + 1, manager[1]), (file_head[0] + 1, file_head[1]), end)


def _cluster_ranges(sheet: SheetData, lo: Layout) -> list[tuple[int, int]]:
    """工程の固まり(行の範囲)。NO の列に番号があるセルが固まりの始まりで、結合セルならその範囲まで。"""
    out, r = [], lo.header_row + 1
    while r < lo.end_row:
        if fold(sheet.text(r, lo.no_col)).isdigit():
            end = sheet.merge_end(r, lo.no_col)
            last = min(end[0] if end else r, lo.end_row - 1)
            out.append((r, last))
            r = last + 1
        else:
            r += 1
    return out


def _name_and_kind(sheet: SheetData, lo: Layout, r1: int, r2: int) -> tuple[str, str]:
    """工程名(固まりの中のセルの文を上から改行でつなぐ)と区分。「社内」「社外」だけの行は区分に入れ、そのすぐ下の INTERNO / EXTERNO だけの行も外す。"""
    lines = [ln.strip() for r in range(r1, r2 + 1) for ln in sheet.text(r, lo.name_col).split("\n")]
    lines = [ln for ln in lines if ln]
    kept, kind, skip_next = [], "none", False
    for ln in lines:
        key = fold(ln)
        if skip_next and key in PORTUGUESE_KINDS:
            skip_next = False
            continue
        skip_next = False
        if key in KINDS:
            kind = kind if kind != "none" else KINDS[key]
            skip_next = True
            continue
        kept.append(ln)
    return "\n".join(kept), kind


def _procedure(sheet: SheetData, lo: Layout, r1: int, r2: int) -> str:
    """作業要領: 固まりの中の1行ごとに、作業要領の列から ライン名の列の手前までの文を空白でつないで1行の文にし、上から改行でつなぐ。前後の空の行は除く(途中の空の行は残す)。"""
    lines: list[str] = []
    for r in range(r1, r2 + 1):
        text = " ".join(p for p in (sheet.text(r, c) for c in range(lo.proc_col, lo.line_col)) if p)
        lines.extend(text.split("\n") if text else [""])
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(ln.rstrip() for ln in lines)


def _row(sheet: SheetData, lo: Layout, r1: int, r2: int, number: int) -> ControlRow:
    name, kind = _name_and_kind(sheet, lo, r1, r2)
    procedure = _procedure(sheet, lo, r1, r2)
    if len(name) > NAME_MAX:
        raise SheetError(f"{number} 番の工程名が長すぎます({len(name)} 文字。上限 {NAME_MAX})")
    if len(procedure) > PROCEDURE_MAX:
        raise SheetError(f"{number} 番の作業要領が長すぎます({len(procedure)} 文字。上限 {PROCEDURE_MAX})")
    use_line = not any(sheet.diagonal(r, lo.line_col) for r in range(r1, r2 + 1))
    return ControlRow(name=name, kind=kind, procedure=procedure, use_line=use_line)  # type: ignore[arg-type]


def _manager_no(sheet: SheetData, lo: Layout) -> str:
    return sheet.text(*lo.manager_cell)


def parse_sheet(sheet: SheetData) -> ParsedSheet:
    """シートを読む。ファイルNo.の形でなければ SheetSkipped、読めなければ SheetError。"""
    key = file_no_of_sheet(sheet.name)
    lo = find_layout(sheet)
    written = sheet.text(*lo.file_cell)
    if written and normalize_file_no(written) != key:
        raise SheetError(f"セットアップファイルNo.の欄({written})がシート名({sheet.name})と違います")
    ranges = _cluster_ranges(sheet, lo)
    if not ranges:
        raise SheetError("工程の行(NO の列の番号)が見つかりません")
    if len(ranges) > MAX_ROWS:
        raise SheetError(f"工程の行が多すぎます({len(ranges)} 行。上限 {MAX_ROWS} 行)")
    numbers = [int(fold(sheet.text(r1, lo.no_col))) for r1, _ in ranges]
    rows = [_row(sheet, lo, r1, r2, n) for (r1, r2), n in zip(ranges, numbers, strict=True)]
    return ParsedSheet(file_no=key, manager_no=_manager_no(sheet, lo), rows=rows)
