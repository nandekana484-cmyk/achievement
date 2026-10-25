"""区間の CSV: 人が入れた文字の列は、式として動く書き出しを避ける(S-03)。識別の列は変えない。詳細: docs/design/security.md"""

from __future__ import annotations

import csv
import datetime as dt
import io

import pytest

from app.core.clock import JST
from app.services.report_csv import FREE_TEXT_HEADERS, HEADERS, intervals_csv, safe_cell
from app.services.report_intervals import IntervalOut


def _row(**kw) -> IntervalOut:
    t = dt.datetime(2026, 10, 21, 9, 0, tzinfo=JST)
    base = dict(
        workday=dt.date(2026, 10, 21), line_code="S", kind="line_event", event_id=1, kitting_no="0722-2-S-251014-01",
    )
    base.update(lot_nos="L001", file_no="0722", product_names="基板A", run_no=1, step_type=None, what="部品探し",
                restart_reason=None, equipment=None, reason_text=None, original_start=t, original_end=t, start=t, end=t,
                minutes=0.0, produced_qty=None, started_by="山田(K1)", ended_by=None, added_later=False, corrected=False, open=False)
    base.update(kw)
    return IntervalOut(**base)


def _cells(row: IntervalOut) -> dict[str, str]:
    text = intervals_csv([row]).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text, newline="")))[0]


@pytest.mark.parametrize("start", ["=", "+", "-", "@", "\t", "\r"])
def test_free_text_cells_get_a_quote_when_they_start_dangerously(start):
    payload = f'{start}HYPERLINK("http://example.invalid","x")'
    cells = _cells(_row(reason_text=payload, restart_reason=payload, equipment=payload, what=payload,
                        product_names=payload, started_by=payload, ended_by=payload))
    for header in ("理由の記入", "再開理由", "設備", "工程または理由", "品名", "開始した人", "終了した人"):
        assert cells[header] == "'" + payload, header


def test_normal_text_is_not_changed():
    cells = _cells(_row(reason_text="部品を探した - 5分", what="部品探し"))
    assert cells["理由の記入"] == "部品を探した - 5分" and cells["工程または理由"] == "部品探し"


def test_identifier_columns_are_never_changed():
    cells = _cells(_row(kitting_no="-0722-2-S-251014-01", lot_nos="=L001", file_no="+0722"))
    assert cells["キッティングNo."] == "-0722-2-S-251014-01"
    assert cells["ロットNo."] == "=L001"
    assert cells["ファイルNo."] == "+0722"


def test_free_text_headers_are_real_columns_and_numbers_stay_numbers():
    assert FREE_TEXT_HEADERS <= set(HEADERS)
    assert safe_cell("") == ""
    assert _cells(_row(minutes=12.5))["時間(分)"] == "12.5"
