from datetime import date

import pytest

from app.domain.kitting_no import KittingNoError, parse_kitting_no


def test_parse_example():
    k = parse_kitting_no("0722-2-S-251014-01")
    assert k.raw == "0722-2-S-251014-01"
    assert k.file_no == "0722"
    assert k.run_no == 2
    assert k.line_code == "S"
    assert k.issue_date == date(2025, 10, 14)
    assert k.issue_seq == 1


def test_strips_whitespace():
    assert parse_kitting_no(" 0722-1-S-251014-03 ").raw == "0722-1-S-251014-03"


def test_issue_order():
    a = parse_kitting_no("0722-1-S-251014-02")
    b = parse_kitting_no("0722-1-S-251015-01")
    assert a.issue_order_key < b.issue_order_key


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0722-3-S-251014-01",  # 回は1か2
        "0722-1-S-2510-01",  # 発行年月日は6桁
        "0722-1-S-251399-01",  # 存在しない日付
        "0722-1-S-251014",  # 発行順がない
        "0722_1_S_251014_01",
    ],
)
def test_invalid(value):
    with pytest.raises(KittingNoError):
        parse_kitting_no(value)
