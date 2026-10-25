"""生産数のロットへの割り振り(実績の書き出し)。"""

from app.domain.allocation import allocate


def test_fills_lots_in_order_up_to_planned_qty():
    assert allocate(120, [100, 50]) == [100, 20]
    assert allocate(150, [100, 50]) == [100, 50]


def test_remainder_goes_to_the_last_lot():
    assert allocate(170, [100, 50]) == [100, 70]
    assert allocate(330, [100, 100, 100]) == [100, 100, 130]


def test_short_total_leaves_later_lots_small_or_zero():
    assert allocate(80, [100, 50, 30]) == [80, 0, 0]
    assert allocate(0, [100, 50]) == [0, 0]


def test_single_lot_gets_everything():
    assert allocate(250, [100]) == [250]


def test_no_lots():
    assert allocate(10, []) == []
