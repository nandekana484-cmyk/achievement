"""NG数と備考(開発指針 5.4)。"""

from app.db.models import RunInput
from records_helpers import K1, LOT, rid, count_rows, set_operator, ok, conflict


def test_ng_qty_latest_is_effective(client, staffed):
    ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 3}))
    r = ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 5}))
    assert (r["kind"], r["value"], r["entered_by_name"]) == ("ng_qty", "5", "山田")
    assert r["entered_at"].endswith("+09:00")
    assert count_rows(RunInput, kind="ng_qty") == 2  # 行を追加する(上書きしない)
    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert plan["ng_qty"] == 5


def test_ng_qty_rules(client, world):
    conflict(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 1}), "担当者が設定されていません")
    set_operator(client, world["yamada"])
    conflict(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": -1}), "0以上の整数")
    assert client.put(f"/api/runs/X/{LOT}/ng-qty", json={"request_id": rid(), "ng_qty": 1}).status_code == 404

    body = {"request_id": rid(), "ng_qty": 2}
    first = ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json=body))
    assert ok(client.put(f"/api/runs/{K1}/{LOT}/ng-qty", json=body)) == first
    assert count_rows(RunInput) == 1


def test_remarks(client, staffed):
    conflict(client.post(f"/api/runs/{K1}/{LOT}/remarks", json={"request_id": rid(), "text": "  "}), "備考が空です")
    r = ok(client.post(f"/api/runs/{K1}/{LOT}/remarks", json={"request_id": rid(), "text": " 部品の向きに注意 ", "operator_id": staffed["sato"]}))
    assert (r["kind"], r["value"], r["entered_by_name"]) == ("remark", "部品の向きに注意", "佐藤")
