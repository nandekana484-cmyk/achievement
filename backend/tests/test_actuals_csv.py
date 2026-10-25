"""実績の書き出しの CSV の形(12列の並びと、列ごとの値)。既存アプリの取込口が列の並びで読むので、変えたら書式版を上げる。"""

import csv
import datetime as dt
import io

from app.core.clock import JST
from app.services.actuals_export import FORMAT_VERSION, HEADERS, actuals_csv
from app.services.actuals_rows import ActualsRowOut

COLUMNS = ["書式版", "書き出し日時", "元のDB(フォルダ名)", "キッティングNo.", "ロットNo.", "ファイルNo.", "面", "日付",
           "生産数(累計)", "NG面1", "NG面2", "担当者ID"]


def _row() -> ActualsRowOut:
    return ActualsRowOut(
        kitting_no="0722-2-S-251014-02", lot_no="0012345", file_no="0722", side=2, line_code="S", product_name="基板",
        planned_qty=300, produced_qty=290, kitting_produced_total=290, kitting_hidden_qty=0, ng_side1=5, ng_side2=3,
        worker_id="ｙ００１", operator_name="山田", completed_on=dt.date(2026, 10, 21), source_db="2026-10",
        side1_kitting_no="0722-1-S-251014-01", exportable=True, warnings=[], notes=[],
    )


def test_header_is_the_12_columns_in_order():
    assert HEADERS == COLUMNS
    assert FORMAT_VERSION == 1


def test_each_column_has_its_value():
    text = actuals_csv([_row()], dt.datetime(2026, 10, 21, 10, 30, 5, tzinfo=JST))
    lines = text.split("\r\n")
    assert lines[0] == ",".join(COLUMNS)
    (got,) = list(csv.DictReader(io.StringIO(text, newline="")))
    assert got == {
        "書式版": "1", "書き出し日時": "2026-10-21 10:30:05", "元のDB(フォルダ名)": "2026-10",
        "キッティングNo.": "0722-2-S-251014-02", "ロットNo.": "0012345", "ファイルNo.": "0722", "面": "2",
        "日付": "2026-10-21", "生産数(累計)": "290", "NG面1": "5", "NG面2": "3", "担当者ID": "ｙ００１",
    }
