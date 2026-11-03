"""生産記録票(AD-18c)の、生産の区切りごとの良品の台数と、数量 A の実績。実績は実績の書き出しと同じ割り振り。"""

from actuals_helpers import admin, finish, listing, login, produce  # noqa: F401
from records_helpers import K1, K2, ok
from test_production_record import K5 as K3, sheet
from test_side_link_field import link, plans


def test_good_qty_per_production_segment(client, admin, fake_clock):
    produce(client, fake_clock, K1, 30, 40)
    finish(client, fake_clock, K1)
    f = sheet(client, K1)["side1"]
    assert [r["good_qty"] for r in f["production"]] == [30, 40]
    assert f["good_total"] == 70


def test_actual_is_the_exported_allocation(client, admin, fake_clock):
    produce(client, fake_clock, K1, 298)  # 計画 300
    finish(client, fake_clock, K1)
    produce(client, fake_clock, K2, 250)
    finish(client, fake_clock, K2)
    ok(link(client, K2, K1))
    lot = sheet(client, K1)["lots"][0]
    assert (lot["produced"], lot["actual"]) == (300, 250)  # 両面の組は面2の行の値
    login(client)
    exported = {(r["kitting_no"], r["lot_no"]): r["produced_qty"] for r in listing(client)}
    assert exported[(K2, "L001")] == lot["actual"]


def test_actual_of_a_one_sided_lot_is_the_face1_value(client, admin, fake_clock):
    plans(admin, (K3, "L060", "1"))
    produce(client, fake_clock, K3, 77)
    finish(client, fake_clock, K3)
    lot = sheet(client, K3)["lots"][0]
    login(client)
    assert lot["actual"] == next(r["produced_qty"] for r in listing(client) if r["kitting_no"] == K3) == 77


def test_actual_is_empty_when_the_face_of_A_is_not_completed(client, admin, fake_clock):
    produce(client, fake_clock, K2, 100)
    finish(client, fake_clock, K2)
    produce(client, fake_clock, K1, 100)  # 面1は片付けが終わっていない
    ok(link(client, K2, K1))
    assert sheet(client, K2)["lots"][0]["actual"] is None
