"""識別票の印刷用のデータ(AD-20): ファイルNo.の表示とSUFの値、4つ目のロットの並び、C の値、取り消した計画は出さない。"""

import pytest

from app.domain.id_slip import display_file_no, suf_value
from actuals_helpers import admin  # noqa: F401
from legacy_fixture import deactivate
from records_helpers import K1, K2, ok, sync_plans
from test_side_link_field import plans


def slips(client, kno):
    return client.get(f"/api/id-slips/{kno}")


@pytest.mark.parametrize("stored, shown", [("0722", "722"), ("0002", "2"), ("1234", "1234"), ("0000", "0"), ("S010", "S010"), ("T207", "T207")])
def test_file_no_display_drops_leading_zeros_of_digits_only(stored, shown):
    assert display_file_no(stored) == shown
    assert suf_value(stored) == "SUF-" + stored  # バーコードの値は保存されている4桁のまま


def test_fields_of_a_plan(client, admin, fake_clock):
    d = ok(slips(client, K1))
    assert (d["file_no"], d["suf"], d["product_name"], d["run_no"], d["line_code"]) == ("722", "SUF-0722", "基板A", 1, "S")
    assert d["kitting_no"] == K1
    assert [(x["lot_no"], x["order_qty"]) for x in d["lots"]] == [("L001", 1000)]  # C = 発注数
    assert ok(slips(client, K2))["run_no"] == 2


def test_all_lots_of_the_kitting_no_in_order(client, admin, fake_clock):
    k = "0722-1-S-251014-07"
    plans(admin, (k, "L012", "1"), (k, "L010", "1"), (k, "L011", "1"))
    d = ok(slips(client, k))
    assert [x["lot_no"] for x in d["lots"]] == ["L010", "L011", "L012"]
    assert d["lot_list"] == "L010, L011, L012"


def test_alphanumeric_file_no_is_kept(client, admin, fake_clock):
    k = "S010-1-S-251014-08"
    plans(admin, (k, "L020", "1"), file_no="S010")
    d = ok(slips(client, k))
    assert (d["file_no"], d["suf"]) == ("S010", "SUF-S010")


def test_unknown_plan_is_not_found(client, admin, fake_clock):
    assert slips(client, "9999-1-S-251014-99").status_code == 404


def test_cancelled_plan_is_refused(client, admin, fake_clock):
    k = "0722-1-S-251014-09"
    plans(admin, (k, "L030", "1"))
    assert ok(slips(client, k))["kitting_no"] == k
    deactivate(admin["db"], k, "L030")
    sync_plans(admin["app"])
    assert slips(client, k).status_code == 409
