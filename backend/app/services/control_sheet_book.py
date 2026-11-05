"""Excel のブック(.xls / .xlsx / .xlsm)を、シートごとの読み取り用の形(SheetData)にする。管理表の内容の取り込み(AD-28)の入り口。

.xls は xlrd(formatting_info=True で開く。罫線の斜線を読むため)、.xlsx と .xlsm は openpyxl(マクロは動かさない。数式は保存されている値)。
行と列は 1 から数える(Excel の表記と同じ)。読んだ中身はログに書かない。詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from typing import Protocol

from app.services.errors import RuleViolation

EXTENSIONS = (".xls", ".xlsx", ".xlsm")
MAX_SHEETS = 2000  # 1つのブックで読むシートの上限
MAX_SCAN_COLS = 60  # 見出しを探す列の数の上限(書式だけが遠くまで続くシートのため)


class SheetData(Protocol):
    name: str
    max_row: int
    max_col: int

    def text(self, row: int, col: int) -> str:
        """セルの文(前後の空白を除く。数は整数ならその文字。空は "")。文の中の改行は残す。"""

    def merge_end(self, row: int, col: int) -> tuple[int, int] | None:
        """(row, col) が結合セルの左上なら、その右下(含む)。そうでなければ None。"""

    def diagonal(self, row: int, col: int) -> bool:
        """セルに斜線の罫線(右上がり・右下がり)があるか。"""


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, bool):
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


class XlsxSheet:
    """openpyxl のシート(.xlsx / .xlsm)。"""

    def __init__(self, ws) -> None:  # noqa: ANN001
        self.ws = ws
        self.name = ws.title
        self.max_row = ws.max_row or 0
        self.max_col = min(ws.max_column or 0, MAX_SCAN_COLS)
        self._merges = {(m.min_row, m.min_col): (m.max_row, m.max_col) for m in ws.merged_cells.ranges}

    def text(self, row: int, col: int) -> str:
        return _text(self.ws.cell(row, col).value)

    def merge_end(self, row: int, col: int) -> tuple[int, int] | None:
        return self._merges.get((row, col))

    def diagonal(self, row: int, col: int) -> bool:
        b = self.ws.cell(row, col).border
        return b is not None and b.diagonal is not None and b.diagonal.style is not None and bool(b.diagonalUp or b.diagonalDown)


class XlsSheet:
    """xlrd のシート(.xls)。"""

    def __init__(self, book, sheet) -> None:  # noqa: ANN001
        self.book, self.sheet = book, sheet
        self.name = sheet.name
        self.max_row = sheet.nrows
        self.max_col = min(sheet.ncols, MAX_SCAN_COLS)
        self._merges = {(rlo + 1, clo + 1): (rhi, chi) for rlo, rhi, clo, chi in sheet.merged_cells}  # xlrd の範囲は 0 始まりで上限を含まない

    def text(self, row: int, col: int) -> str:
        import xlrd

        if row > self.sheet.nrows or col > self.sheet.ncols:
            return ""
        cell = self.sheet.cell(row - 1, col - 1)
        if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK, xlrd.XL_CELL_ERROR, xlrd.XL_CELL_BOOLEAN):
            return ""
        return _text(cell.value)

    def merge_end(self, row: int, col: int) -> tuple[int, int] | None:
        return self._merges.get((row, col))

    def diagonal(self, row: int, col: int) -> bool:
        try:
            border = self.book.xf_list[self.sheet.cell_xf_index(row - 1, col - 1)].border
        except (IndexError, KeyError):
            return False
        return border.diag_line_style != 0 and bool(border.diag_up or border.diag_down)


def open_sheets(data: bytes, filename: str) -> Iterator[SheetData]:
    """ブックのシートを順に返す。形式が違う・壊れている・パスワード付きなどで読めなければ RuleViolation(中身は出さない)。"""
    name = filename.lower()
    if not name.endswith(EXTENSIONS):
        raise RuleViolation("取り込めるのは Excel のブック(.xls、.xlsx、.xlsm)だけです")
    try:
        if name.endswith(".xls"):
            import xlrd

            book = xlrd.open_workbook(file_contents=data, formatting_info=True)
            names = book.sheet_names()
            _check_count(len(names))
            sheets = (XlsSheet(book, book.sheet_by_index(i)) for i in range(len(names)))
        else:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, keep_vba=False, keep_links=False)
            _check_count(len(wb.worksheets))
            sheets = (XlsxSheet(ws) for ws in wb.worksheets)
        yield from sheets
    except RuleViolation:
        raise
    except Exception as e:  # noqa: BLE001  形式が違う・壊れている・パスワード付きなど。理由に中身を含めない(例外の種類だけ)
        raise RuleViolation(f"ブックを読めませんでした(形式が違う、壊れている、パスワードが付いている、など。{type(e).__name__})") from None


def _check_count(count: int) -> None:
    if count > MAX_SHEETS:
        raise RuleViolation(f"シートが多すぎます({count} 枚。上限 {MAX_SHEETS} 枚)")
