"""計画のまとまり(キッティングNo.ごと)の計算。DBに触らない。"""

from dataclasses import dataclass
from datetime import datetime

from app.core.clock import JST
from app.services.kitting_plans import group_lots, mismatch_warnings, sort_groups


@dataclass
class Lot:
    kitting_no: str
    lot_no: str
    planned_qty: int = 100
    product_name: str = "基板"
    file_no: str = "0722"
    line_code: str = "S"
    run_no: int = 1
    planned_start: datetime | None = datetime(2026, 10, 21, 9, 0, tzinfo=JST)
    planned_end: datetime | None = datetime(2026, 10, 21, 12, 0, tzinfo=JST)
    takt_sec: float | None = 30.0
    status: str = "active"


def _by_status(lot: Lot) -> str:
    return lot.status


def test_group_sums_quantities_and_keeps_shared_values():
    [g] = group_lots([Lot("K1", "L2", 200, "基板B"), Lot("K1", "L1", 100, "基板A")])
    assert [lot.lot_no for lot in g.lots] == ["L1", "L2"]  # ロットNo.の順
    assert (g.planned_qty, g.file_no, g.line_code, g.run_no, g.takt_sec) == (300, "0722", "S", 1, 30.0)
    assert g.product_name == "基板A"  # 最初のロットの基板名
    assert g.status == "active" and g.warnings == []


def test_groups_are_per_kitting_no():
    groups = sort_groups(group_lots([
        Lot("K2", "L1", planned_start=datetime(2026, 10, 21, 13, 0, tzinfo=JST)), Lot("K1", "L1"), Lot("K1", "L2"),
        Lot("K3", "L1", planned_start=None, planned_end=None),
    ]))
    assert [(g.kitting_no, len(g.lots)) for g in groups] == [("K1", 2), ("K2", 1), ("K3", 1)]  # 日程が空のものは最後


def test_partly_cancelled_uses_remaining_lots():
    [g] = group_lots([Lot("K1", "L1", 100), Lot("K1", "L2", 200, status="cancelled")], _by_status)
    assert [lot.lot_no for lot in g.lots] == ["L1"] and g.planned_qty == 100 and g.status == "active"


def test_all_cancelled_makes_group_cancelled():
    [g] = group_lots([Lot("K1", "L1", status="cancelled"), Lot("K1", "L2", status="cancelled")], _by_status)
    assert g.status == "cancelled" and len(g.lots) == 2


def test_differing_values_warn_and_use_earliest_latest_first():
    early = datetime(2026, 10, 21, 8, 0, tzinfo=JST)
    late = datetime(2026, 10, 21, 14, 0, tzinfo=JST)
    [g] = group_lots([
        Lot("K1", "L1", file_no="0722"),
        Lot("K1", "L2", file_no="0800", line_code="T", planned_start=early, planned_end=late),
    ])
    assert g.planned_start == early and g.planned_end == late  # 計画開始は最も早く、終了は最も遅く
    assert (g.file_no, g.line_code) == ("0722", "S")  # それ以外は最初のロット
    assert len(g.warnings) == 4
    assert any("ファイルNo.が違います" in w for w in g.warnings)
    assert any("ラインが違います" in w for w in g.warnings)


def test_mismatch_warnings_for_side():
    assert mismatch_warnings("K1", [Lot("K1", "L1", run_no=1), Lot("K1", "L2", run_no=2)]) == [
        "キッティングNo. K1 のロットで面が違います(計画開始は最も早いもの、計画終了は最も遅いもの、それ以外は最初のロットの値を使います)",
    ]
    assert mismatch_warnings("K1", [Lot("K1", "L1"), Lot("K1", "L2")]) == []
