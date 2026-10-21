"""計画の検索(GET /api/plans/search)。"""

from datetime import datetime

import pytest

from app.core.clock import JST
from legacy_fixture import deactivate, insert_plan
from records_helpers import ok, sync_plans


@pytest.fixture
def plans(client, world, fake_clock):
    db = world["db"]
    insert_plan(db, kitting_no="0722-1-S-251018-01", lot_no="LOT-A01", file_no="0722", board="制御基板ＡＢＣ",
                start="2026/10/18 09:00:00", end="2026/10/18 12:00:00")
    insert_plan(db, kitting_no="0722-2-S-251018-02", lot_no="LOT-A01", file_no="0722", side="2", board="制御基板ＡＢＣ",
                start="2026/10/21 09:00:00", end="2026/10/21 12:00:00")
    insert_plan(db, kitting_no="T458-1-T-251018-03", lot_no="lot-b02", file_no="T458", line="T", board="表示基板",
                start="2026/10/30 09:00:00", end="2026/10/30 12:00:00")
    insert_plan(db, kitting_no="0999-1-S-251018-04", lot_no="LOT-C03", file_no="0999", board="取消になる基板",
                start="2026/10/21 10:00:00", end="2026/10/21 11:00:00")
    sync_plans(world["app"])
    deactivate(db, "0999-1-S-251018-04", "LOT-C03")
    sync_plans(world["app"])
    return world


def _search(client, q, **params):
    return [p["kitting_no"] for p in ok(client.get("/api/plans/search", params={"q": q, **params}))]


def test_partial_match_on_kitting_no_lot_and_name(client, plans):
    assert _search(client, "251018-03") == ["T458-1-T-251018-03"]
    assert _search(client, "A01") == ["0722-2-S-251018-02", "0722-1-S-251018-01"]  # 計画開始が今に近い順
    assert _search(client, "表示") == ["T458-1-T-251018-03"]


def test_case_and_width_are_ignored(client, plans):
    assert _search(client, "t458") == ["T458-1-T-251018-03"]  # 小文字
    assert _search(client, "ＬＯＴ－Ｂ０２") == ["T458-1-T-251018-03"]  # 全角
    assert _search(client, "abc") == ["0722-2-S-251018-02", "0722-1-S-251018-01"]  # 品名の全角英字
    assert _search(client, "  0722-1-s-251018-01 ") == ["0722-1-S-251018-01"]  # 完全に一致する1件(前後の空白も無視)


def test_cancelled_plans_are_not_found(client, plans):
    assert _search(client, "取消") == []
    assert _search(client, "0999") == []


def test_line_filter_and_empty_query(client, plans):
    assert _search(client, "LOT", line_code="t") == ["T458-1-T-251018-03"]  # ラインの記号は正規化する
    assert _search(client, "   ") == []


def test_at_most_20_results_nearest_first(client, world, fake_clock):
    for i in range(25):
        insert_plan(world["db"], kitting_no=f"{i + 100:04d}-1-S-251018-{i:02d}", file_no=f"{i + 100:04d}",
                    start=f"2026/10/{i + 1:02d} 09:00:00", end=f"2026/10/{i + 1:02d} 10:00:00")
    sync_plans(world["app"])
    fake_clock.current = datetime(2026, 10, 21, 8, 0, tzinfo=JST)
    found = _search(client, "-251018-")
    assert len(found) == 20
    assert found[0] == "0120-1-S-251018-20"  # 10/21 9:00 が今(10/21 8:00)にいちばん近い
