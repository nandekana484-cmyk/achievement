"""管理表の内容の Excel 取り込み(AD-28)の読み方: 見出しの位置、ファイルNo.の直し方、固まり、社内と INTERNO、作業要領、斜線、空の固まり、飛ばすシート。DBには触れない。"""

import pytest
from book_helpers import Cluster, SheetSpec, build_xls, build_xlsx, example_sheet

from app.services.control_sheet_import import read_book
from app.services.control_sheet_parse import normalize_file_no

BUILDERS = [pytest.param((build_xlsx, "t.xlsx"), id="xlsx"), pytest.param((build_xls, "t.xls"), id="xls")]


def read(builder, *specs):
    build, filename = builder
    return read_book(build(*specs), filename)


def one(builder, spec):
    (o,) = read(builder, spec)
    assert o.parsed is not None, o.error or o.skipped
    return o.parsed


@pytest.mark.parametrize("raw, key", [("722", "0722"), (" 722 ", "0722"), ("７２２", "0722"), ("0722", "0722"), ("s010", "S010"), ("ｓ０１０", "S010"), ("　T207　", "T207"), (722.0, "0722")])
def test_file_no_normalization(raw, key):
    assert normalize_file_no(str(int(raw)) if isinstance(raw, float) else raw) == key


@pytest.mark.parametrize("builder", BUILDERS)
def test_template_positions(builder):
    p = one(builder, example_sheet())
    assert (p.file_no, p.manager_no, len(p.rows)) == ("0722", "MP-1", 3)
    r1, r2, r3 = p.rows
    assert (r1.name, r1.kind, r1.procedure, r1.use_line) == ("SMT-1\n(リフロー)", "internal", "Side B", True)  # 社内・INTERNO は区分に入れて、工程名から外す
    assert (r2.name, r2.kind) == ("X線検査\nInspeção de Raio X", "internal")
    assert r2.procedure == "ロケーション\n\n検査数 5 枚"  # C〜G の文は空白でつなぎ、途中の空の行は残し、後ろの空の行は除く
    assert r2.use_line is False  # 斜線
    assert (r3.name, r3.procedure, r3.use_line, r3.kind) == ("", "", True, "none")  # 中身の無い固まりも空の行として取り込む
    assert all(r.name_vi is None and r.link == "none" for r in p.rows)


@pytest.mark.parametrize("builder", BUILDERS)
def test_headings_are_searched_not_fixed(builder):
    p = one(builder, example_sheet(dr=3, dc=2))  # 全体を下へ3行、右へ2列ずらしても同じに読める
    assert (p.manager_no, [r.name for r in p.rows][:1]) == ("MP-1", ["SMT-1\n(リフロー)"])


def test_headings_ignore_spaces_and_width():
    from book_helpers import _write  # noqa: F401

    spec = example_sheet()
    data = build_xlsx(spec)
    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws = wb.active
    ws["L1"] = "　管理Ｎｏ "  # 全角・前後の全角空白
    ws["B15"] = "工程　名"
    ws["H15"] = " ライン名　"
    out = io.BytesIO()
    wb.save(out)
    (o,) = read_book(out.getvalue(), "t.xlsx")
    assert o.parsed is not None and o.parsed.manager_no == "MP-1"


@pytest.mark.parametrize("missing, word", [("manager", "管理No"), ("file", "セットアップファイル"), ("no", "NO"), ("name", "工程名"), ("proc", "作業要領"), ("line", "ライン名"), ("assembly", "組立工程へ")])
def test_missing_heading_is_an_error(missing, word):
    (o,) = read_book(build_xlsx(example_sheet(skip={missing})), "t.xlsx")
    assert o.parsed is None and o.error and word in o.error


def test_manager_no_number_is_an_integer_text():
    assert one(BUILDERS[0].values[0], example_sheet(manager_no=12.0)).manager_no == "12"
    assert one(BUILDERS[0].values[0], example_sheet(manager_no="  MP-9  ")).manager_no == "MP-9"
    assert one(BUILDERS[0].values[0], example_sheet(manager_no=None)).manager_no == ""


def test_file_no_cell_must_match_the_sheet_name():
    ok = example_sheet(name="0722", file_no_cell="７２２")  # 同じ規則で直して一致すればよい
    assert one(BUILDERS[0].values[0], ok).file_no == "0722"
    (o,) = read_book(build_xlsx(example_sheet(name="0722", file_no_cell=800)), "t.xlsx")
    assert o.parsed is None and "0800" not in (o.error or "") and "シート名" in o.error
    assert one(BUILDERS[0].values[0], example_sheet(name="0722", file_no_cell="")).file_no == "0722"  # 空ならシート名だけ


def test_sheets_that_are_not_file_nos_are_skipped():
    out = read_book(build_xlsx(example_sheet("Sheet1"), example_sheet("説明"), example_sheet("722"), example_sheet("s010", file_no_cell="")), "t.xlsx")
    assert [(o.sheet_name, o.skipped is not None, o.file_no) for o in out] == [("Sheet1", True, None), ("説明", True, None), ("722", False, "0722"), ("s010", False, "S010")]
    assert "ファイルNo.の形" in (out[0].skipped or "")


def test_duplicate_file_no_sheets_are_errors():
    out = read_book(build_xlsx(example_sheet("722"), example_sheet("0722", file_no_cell="")), "t.xlsx")
    assert out[0].parsed is not None and out[1].parsed is None and "同じファイルNo." in (out[1].error or "")


@pytest.mark.parametrize("builder", BUILDERS)
def test_clusters_of_different_heights_and_numbers_beyond_8(builder):
    clusters = [Cluster(i + 1, [f"工程{i + 1}"] * (1 + i % 4), [f"作業{i + 1}"], rows=1 + (i * 3) % 5) for i in range(10)]  # 番号は10まで。行の数はまちまち
    p = one(builder, SheetSpec(name="1000", manager_no="M", file_no_cell="1000", clusters=clusters))
    assert len(p.rows) == 10
    assert [r.procedure for r in p.rows] == [f"作業{i + 1}" for i in range(10)]
    assert p.rows[3].name == "\n".join(["工程4"] * 4)  # 固まりの中のセルの文を上から改行でつなぐ


@pytest.mark.parametrize("builder", BUILDERS)
def test_diagonal_up_down_and_none(builder):
    clusters = [Cluster(1, ["A"], diagonal="up"), Cluster(2, ["B"], diagonal="down"), Cluster(3, ["C"]), Cluster(4, ["D", "E"], rows=3, diagonal="up")]
    p = one(builder, SheetSpec(name="0001", file_no_cell="", clusters=clusters))
    assert [r.use_line for r in p.rows] == [False, False, True, False]  # 斜線があれば「使わない」


def test_kind_and_portuguese_lines():
    clusters = [
        Cluster(1, ["外注", "社外", "EXTERNO"]),  # 社外 → 区分、すぐ下の EXTERNO も外す
        Cluster(2, ["社内", "検査", "INTERNO"]),  # 社内の下が INTERNO でなければ外さない。あとの INTERNO(すぐ下ではない)は残る
        Cluster(3, ["ＳＭＴ", "　社内　", "ｉｎｔｅｒｎｏ"]),  # 全角・空白・小文字は無視
        Cluster(4, ["そのまま"]),
    ]
    rows = one(BUILDERS[0].values[0], SheetSpec(name="0002", clusters=clusters)).rows
    assert [(r.name, r.kind) for r in rows] == [("外注", "external"), ("検査\nINTERNO", "internal"), ("ＳＭＴ", "internal"), ("そのまま", "none")]


def test_procedure_lines():
    cl = Cluster(1, ["P"], ["", "  先頭の空行は除く  ", "", "途中の空行は残す", ""], proc_extra={1: ["と", "続き"], 3: ["B"]})
    p = one(BUILDERS[0].values[0], SheetSpec(name="0003", clusters=[cl]))
    assert p.rows[0].procedure == "先頭の空行は除く と 続き\n\n途中の空行は残す B"


def test_cell_formula_uses_the_saved_value_and_too_long_is_an_error():
    long_name = "あ" * 101
    (o,) = read_book(build_xlsx(SheetSpec(name="0004", clusters=[Cluster(1, [long_name])])), "t.xlsx")
    assert o.parsed is None and "工程名が長すぎます" in (o.error or "")
    (o,) = read_book(build_xlsx(SheetSpec(name="0005", clusters=[Cluster(1, ["P"], ["x" * 2001])])), "t.xlsx")
    assert o.parsed is None and "作業要領が長すぎます" in (o.error or "")
    (o,) = read_book(build_xlsx(SheetSpec(name="0006", clusters=[])), "t.xlsx")
    assert o.parsed is None and "工程の行" in (o.error or "")


def test_formula_cells_use_saved_values(tmp_path):
    import io

    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(build_xlsx(example_sheet())))
    wb.active["L2"] = "=1+1"  # 保存されている値は無い(openpyxl は計算しない)ので、空として読む。数式の文字は使わない
    out = io.BytesIO()
    wb.save(out)
    (o,) = read_book(out.getvalue(), "t.xlsx")
    assert o.parsed is not None and o.parsed.manager_no == ""


def test_not_a_workbook_and_bad_extension():
    from app.services.errors import RuleViolation

    with pytest.raises(RuleViolation, match="ブックを読めませんでした"):
        read_book(b"not a workbook", "t.xlsx")
    with pytest.raises(RuleViolation, match="ブックを読めませんでした"):
        read_book(b"not a workbook", "t.xls")
    with pytest.raises(RuleViolation, match=r"\.xls"):
        read_book(b"x", "t.csv")


def test_xlsm_extension_is_read_like_xlsx():
    (o,) = read_book(build_xlsx(example_sheet()), "t.xlsm")
    assert o.parsed is not None and len(o.parsed.rows) == 3


def test_sheet_count_limit(monkeypatch):
    from app.services import control_sheet_book
    from app.services.errors import RuleViolation

    monkeypatch.setattr(control_sheet_book, "MAX_SHEETS", 2)
    with pytest.raises(RuleViolation, match="シートが多すぎます"):
        read_book(build_xlsx(example_sheet("0001"), example_sheet("0002"), example_sheet("0003")), "t.xlsx")
