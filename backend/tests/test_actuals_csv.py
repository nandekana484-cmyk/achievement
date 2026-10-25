"""実績の書き出しの CSV の形(13列の並びと、列ごとの値)。既存アプリの取込口が列の並びで読むので、変えたら書式版を上げる。"""

import csv
import datetime as dt
import io

from app.core.clock import JST
from app.services.actuals_export import FORMAT_VERSION, HEADERS, actuals_csv
from app.services.actuals_rows import ActualsRowOut

COLUMNS = ["書式版", "書き出し日時", "元のDB(フォルダ名)", "キッティングNo.", "ロットNo.", "ファイルNo.", "面", "日付",
           "生産数(累計)", "NG面1", "NG面2", "担当者ID", "面1のキッティングNo."]


def _row() -> ActualsRowOut:
    return ActualsRowOut(
        kitting_no="0722-2-S-251014-02", lot_no="0012345", file_no="0722", side=2, line_code="S", product_name="基板",
        planned_qty=300, produced_qty=290, kitting_produced_total=290, kitting_hidden_qty=0, ng_side1=5, ng_side2=3,
        worker_id="ｙ００１", operator_name="山田", completed_on=dt.date(2026, 10, 21), source_db="2026-10",
        side1_kitting_no="0722-1-S-251014-01", exportable=True, warnings=[], notes=[],
    )


def test_header_is_the_13_columns_in_order():
    assert HEADERS == COLUMNS and len(HEADERS) == 13
    assert HEADERS[-1] == "面1のキッティングNo."  # 最後に足した(前の12列の並びは変えない)
    assert FORMAT_VERSION == 2


def test_each_column_has_its_value():
    text = actuals_csv([_row()], dt.datetime(2026, 10, 21, 10, 30, 5, tzinfo=JST))
    lines = text.split("\r\n")
    assert lines[0] == ",".join(COLUMNS)
    (got,) = list(csv.DictReader(io.StringIO(text, newline="")))
    assert got == {
        "書式版": "2", "書き出し日時": "2026-10-21 10:30:05", "元のDB(フォルダ名)": "2026-10",
        "キッティングNo.": "0722-2-S-251014-02", "ロットNo.": "0012345", "ファイルNo.": "0722", "面": "2",
        "日付": "2026-10-21", "生産数(累計)": "290", "NG面1": "5", "NG面2": "3", "担当者ID": "ｙ００１",
        "面1のキッティングNo.": "0722-1-S-251014-01",
    }


def _got(row: ActualsRowOut) -> dict[str, str]:
    (got,) = list(csv.DictReader(io.StringIO(actuals_csv([row], dt.datetime(2026, 10, 21, 10, 30, 5, tzinfo=JST)), newline="")))
    return got


def test_side1_kitting_no_is_filled_even_when_ng_side1_is_zero():
    got = _got(_row().model_copy(update={"ng_side1": 0}))
    assert got["NG面1"] == "0" and got["面1のキッティングNo."] == "0722-1-S-251014-01"


def test_side1_kitting_no_is_empty_for_side1_rows_and_for_side2_rows_without_a_side1():
    side1_row = _row().model_copy(update={"kitting_no": "0722-1-S-251014-01", "side": 1, "side1_kitting_no": None})
    assert _got(side1_row)["面1のキッティングNo."] == ""
    alone = _row().model_copy(update={"side1_kitting_no": None})
    assert _got(alone)["面1のキッティングNo."] == ""


def test_exported_at_is_fixed_to_japan_time_without_timezone():
    utc = dt.datetime(2026, 10, 21, 1, 30, 5, tzinfo=dt.timezone.utc)  # 日本時間 10:30:05
    (got,) = list(csv.DictReader(io.StringIO(actuals_csv([_row()], utc), newline="")))
    assert got["書き出し日時"] == "2026-10-21 10:30:05"
    assert "+" not in got["書き出し日時"] and "T" not in got["書き出し日時"]
