"""NG数(ロットと、NGが出た面を選んで入力する)。

world の計画: K1 = 0722 の面1(ロット L001)、K2 = 0722 の面2(ロット L001)。
"""

import pytest

from app.db.models import RunNgInput
from legacy_fixture import insert_plan
from records_helpers import K1, K2, count_rows, ok, conflict, rid, set_operator, sync_plans


def ng(client, kitting_no, lot_no, side, qty, **extra):
    return client.put(f"/api/runs/{kitting_no}/ng-qty", json={"request_id": rid(), "lot_no": lot_no, "side": side, "ng_qty": qty, **extra})


def _board_plan(client, kitting_no):
    b = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    return next(p for p in b["plans"] if p["plan"]["kitting_no"] == kitting_no)


def test_side1_plan_accepts_only_side1(client, staffed):
    r = ok(ng(client, K1, "L001", 1, 3))
    assert (r["kitting_no"], r["lot_no"], r["side"], r["side_kitting_no"], r["ng_qty"]) == (K1, "L001", 1, K1, 3)
    conflict(ng(client, K1, "L001", 2, 1), "面1の計画では、面2のNGは入力できません")
    assert _board_plan(client, K1)["ng_choices"] == [{"lot_no": "L001", "sides": [1], "side1_kitting_no": None, "note": None}]


def test_side2_plan_accepts_side1_of_matching_plan(client, staffed):
    r = ok(ng(client, K2, "L001", 1, 2))  # 面2の計画から、同じロットの面1のNGも入力する
    assert (r["kitting_no"], r["side"], r["side_kitting_no"]) == (K2, 1, K1)  # 面1の計画のキッティングNo.も記録
    r = ok(ng(client, K2, "L001", 2, 4))
    assert (r["side"], r["side_kitting_no"]) == (2, K2)
    assert _board_plan(client, K2)["ng_choices"] == [{"lot_no": "L001", "sides": [1, 2], "side1_kitting_no": K1, "note": None}]


def test_side2_plan_without_side1_plan_cannot_choose_side1(client, staffed):
    # 同じロットNo.・同じファイルNo.の面1の計画が無い面2の計画
    insert_plan(staffed["db"], kitting_no="0800-2-S-251014-05", lot_no="L777", file_no="0800", side="2",
                start="2026/10/21 15:00:00", end="2026/10/21 17:00:00")
    sync_plans(staffed["app"])
    kno = "0800-2-S-251014-05"
    conflict(ng(client, kno, "L777", 1, 1), "同じロットの面1の計画が見つからないため、面1は選べません")
    ok(ng(client, kno, "L777", 2, 1))
    [choice] = _board_plan(client, kno)["ng_choices"]
    assert choice["sides"] == [2] and "面1は選べません" in choice["note"]


def test_side1_plan_must_have_same_file_no(client, staffed):
    # 同じロットNo.でも、ファイルNo.が違う面1の計画は対応しない
    insert_plan(staffed["db"], kitting_no="0900-2-S-251014-06", lot_no="L001", file_no="0900", side="2",
                start="2026/10/21 15:00:00", end="2026/10/21 17:00:00")
    sync_plans(staffed["app"])
    conflict(ng(client, "0900-2-S-251014-06", "L001", 1, 1), "面1は選べません")


def test_lot_and_side_must_be_valid(client, staffed):
    conflict(ng(client, K1, "L999", 1, 1), "ロットNo. L999 は、この計画のロットではありません")
    conflict(ng(client, K1, "L001", 3, 1), "面は1か2を選んでください")
    conflict(ng(client, K1, "L001", 1, -1), "0以上の整数")
    assert ng(client, "9999-1-S-251014-99", "L001", 1, 1).status_code == 404


def test_requires_operator(client, world):
    conflict(ng(client, K1, "L001", 1, 1), "担当者が設定されていません")
    set_operator(client, world["yamada"])
    ok(ng(client, K1, "L001", 1, 1))


def test_latest_value_per_lot_and_side_is_effective(client, staffed):
    ok(ng(client, K2, "L001", 2, 3))
    ok(ng(client, K2, "L001", 2, 5))  # 同じロット・面 → 最新の値を有効とする
    ok(ng(client, K2, "L001", 1, 1))
    assert count_rows(RunNgInput) == 3  # 過去の値は履歴として残す
    entries = [(e["lot_no"], e["side"], e["ng_qty"]) for e in _board_plan(client, K2)["ng_entries"]]
    assert entries == [("L001", 1, 1), ("L001", 2, 5)]
    assert _board_plan(client, K1)["ng_entries"] == []  # 面1のNGでも、入力した計画(K2)に付く


def test_ng_is_idempotent(client, staffed):
    body = {"request_id": rid(), "lot_no": "L001", "side": 1, "ng_qty": 2}
    first = ok(client.put(f"/api/runs/{K1}/ng-qty", json=body))
    assert ok(client.put(f"/api/runs/{K1}/ng-qty", json=body)) == first
    conflict(client.put(f"/api/runs/{K1}/ng-qty", json={**body, "ng_qty": 3}), "同じリクエストIDで")
    assert count_rows(RunNgInput) == 1


@pytest.mark.parametrize("missing", ["lot_no", "side"])
def test_lot_and_side_are_required(client, staffed, missing):
    body = {"request_id": rid(), "lot_no": "L001", "side": 1, "ng_qty": 2}
    del body[missing]
    assert client.put(f"/api/runs/{K1}/ng-qty", json=body).status_code == 422
