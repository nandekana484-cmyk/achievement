"""管理表の内容の取り込み(AD-28)のテスト用に、ユーザーのテンプレートと同じ形のブックをコードで作る(ユーザーの Excel はリポジトリに入れない)。

位置はテンプレートのとおり(行と列は Excel の表記): 管理No の見出し L1・値 L2(L2:N2 結合)、セットアップファイル№ の見出し A3・値 A4(A4:B5 結合)、
製品名 C6(C6:N7 結合)、表の見出し 15行目(A「NO」、B「工程名」、C「作業要領･注意点」、H「ライン名」)、16行目はポルトガル語の見出し、
工程の行は17行目から(A列の番号は縦に結合)、表の終わりは C列の「・組立工程へ」の行。.xlsx は openpyxl、.xls は xlwt(開発用。製品には入れない)で書く。
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field


@dataclass
class Cluster:
    """工程の固まり1つ。name_cells / proc_cells は行ごとの文(固まりの行数 = 長いほう)。proc_extra は D〜G 列の文(行ごと)。"""

    no: int | str
    name_cells: list[str] = field(default_factory=list)
    proc_cells: list[str] = field(default_factory=list)
    proc_extra: dict[int, list[str]] = field(default_factory=dict)  # 行の番号(0 始まり) → D, E, ... 列の文
    diagonal: str | None = None  # None / "up" / "down"
    rows: int | None = None  # 行数(省略すると、文の行数と1の大きいほう)

    def height(self) -> int:
        return self.rows or max(len(self.name_cells), len(self.proc_cells), 1)


@dataclass
class SheetSpec:
    name: str
    manager_no: object = ""
    file_no_cell: object = ""
    clusters: list[Cluster] = field(default_factory=list)
    dr: int = 0  # 全体を下へずらす行数(見出しの位置を固定しないことの確認用)
    dc: int = 0  # 全体を右へずらす列数
    skip: set[str] = field(default_factory=set)  # 書かない見出し: manager / file / no / name / proc / line / assembly


def _write(spec: SheetSpec, put, merge, diagonal) -> None:
    """put(row, col, value) / merge(r1, c1, r2, c2, value) / diagonal(r1, r2, col, kind) は形式ごとの書き方(行と列は 1 から)。"""
    r0, c0 = spec.dr, spec.dc
    if "manager" not in spec.skip:
        put(1 + r0, 12 + c0, "管理No")
    merge(2 + r0, 12 + c0, 2 + r0, 14 + c0, spec.manager_no)
    if "file" not in spec.skip:
        put(3 + r0, 1 + c0, "セットアップファイル№")
    merge(4 + r0, 1 + c0, 5 + r0, 2 + c0, spec.file_no_cell)
    merge(6 + r0, 3 + c0, 7 + r0, 14 + c0, "テスト製品名")  # 取り込みには使わない
    h = 15 + r0
    for key, col, label in (("no", 1, "NO"), ("name", 2, "工程名"), ("proc", 3, "作業要領･注意点"), ("line", 8, "ライン名")):
        if key not in spec.skip:
            put(h, col + c0, label)
    put(h + 1, 2 + c0, "NOME DO PROCESSO")  # 16行目はポルトガル語の見出し
    r = h + 2
    for cl in spec.clusters:
        n = cl.height()
        merge(r, 1 + c0, r + n - 1, 1 + c0, cl.no)
        for i in range(n):
            if i < len(cl.name_cells) and cl.name_cells[i]:
                put(r + i, 2 + c0, cl.name_cells[i])
            if i < len(cl.proc_cells) and cl.proc_cells[i]:
                put(r + i, 3 + c0, cl.proc_cells[i])
            for j, text in enumerate(cl.proc_extra.get(i, [])):
                put(r + i, 4 + c0 + j, text)
        if cl.diagonal:  # 斜線つきのライン名の欄(縦に結合)。結合と罫線は形式ごとの diagonal が書く
            diagonal(r, r + n - 1, 8 + c0, cl.diagonal)
        else:
            merge(r, 8 + c0, r + n - 1, 8 + c0, None)
        r += n
    if "assembly" not in spec.skip:
        put(r, 3 + c0, "・組立工程へ")


def build_xlsx(*specs: SheetSpec) -> bytes:
    import openpyxl
    from openpyxl.styles import Border, Side

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for spec in specs:
        ws = wb.create_sheet(spec.name)

        def put(r, c, v, ws=ws):
            ws.cell(r, c).value = v

        def merge(r1, c1, r2, c2, v, ws=ws):
            if (r1, c1) != (r2, c2):
                ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
            ws.cell(r1, c1).value = v

        def diagonal(r1, r2, c, kind, ws=ws):
            if r2 > r1:
                ws.merge_cells(start_row=r1, start_column=c, end_row=r2, end_column=c)
            ws.cell(r1, c).border = Border(diagonal=Side(style="thin"), diagonalUp=kind == "up", diagonalDown=kind == "down")

        _write(spec, put, merge, diagonal)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def build_xls(*specs: SheetSpec) -> bytes:
    import xlwt

    wb = xlwt.Workbook(encoding="utf-8")
    for spec in specs:
        ws = wb.add_sheet(spec.name)

        def put(r, c, v, ws=ws):
            ws.write(r - 1, c - 1, "" if v is None else v)

        def merge(r1, c1, r2, c2, v, ws=ws):
            if (r1, c1) != (r2, c2):
                ws.write_merge(r1 - 1, r2 - 1, c1 - 1, c2 - 1, "" if v is None else v)
            else:
                ws.write(r1 - 1, c1 - 1, "" if v is None else v)

        def diagonal(r1, r2, c, kind, ws=ws):
            style = xlwt.XFStyle()
            style.borders = xlwt.Borders()
            style.borders.diag = xlwt.Borders.THIN
            style.borders.need_diag1 = 1 if kind == "down" else 0
            style.borders.need_diag2 = 1 if kind == "up" else 0
            ws.write_merge(r1 - 1, r2 - 1, c - 1, c - 1, "", style) if r2 > r1 else ws.write(r1 - 1, c - 1, "", style)

        _write(spec, put, merge, diagonal)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def example_sheet(name: str = "0722", **over) -> SheetSpec:
    """様式の例(SMT-1 と X線検査と空の固まり)に近い、よくある1シート。"""
    clusters = [
        Cluster(1, ["SMT-1", "(リフロー)", "社内", "INTERNO"], ["Side B"]),
        Cluster(2, ["X線検査", "Inspeção de Raio X", "社内", "INTERNO"], ["ロケーション", "", "検査数", ], proc_extra={2: ["5", "枚"]}, diagonal="up"),
        Cluster(3, [], [], rows=2),
    ]
    return SheetSpec(**{"name": name, "manager_no": "MP-1", "file_no_cell": 722, "clusters": clusters, **over})
