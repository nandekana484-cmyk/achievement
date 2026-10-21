"""備考(開発指針 5.4)。キッティングNo.の単位。"""

from records_helpers import K1, ok, conflict, rid


def test_remarks(client, staffed):
    conflict(client.post(f"/api/runs/{K1}/remarks", json={"request_id": rid(), "text": "  "}), "備考が空です")
    r = ok(client.post(f"/api/runs/{K1}/remarks", json={"request_id": rid(), "text": " 部品の向きに注意 ", "operator_id": staffed["sato"]}))
    assert (r["kitting_no"], r["kind"], r["value"], r["entered_by_name"]) == (K1, "remark", "部品の向きに注意", "佐藤")
    assert "lot_no" not in r


def test_remark_unknown_plan_is_404(client, staffed):
    assert client.post("/api/runs/9999-1-S-251014-99/remarks", json={"request_id": rid(), "text": "x"}).status_code == 404
