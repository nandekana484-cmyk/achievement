"""今の担当者(開発指針 5.6)。"""

from sqlalchemy import select

from app.db.models import LineOperator
from records_helpers import rid, new_session, count_rows, set_operator, conflict


def test_current_operator_change(client, world, fake_clock):
    assert client.get("/api/lines/S/operator").json() is None

    first = set_operator(client, world["yamada"])
    assert (first["operator_id"], first["operator_name"]) == (world["yamada"], "山田")
    assert first["start_at"] == "2026-10-21T08:00:00+09:00"

    fake_clock.advance(hours=2)
    set_operator(client, world["sato"])

    now = client.get("/api/lines/S/operator").json()
    assert now["operator_name"] == "佐藤" and now["start_at"] == "2026-10-21T10:00:00+09:00"
    with new_session() as s:  # 交代すると前の行に end_at が入る(行は消さない)
        rows = list(s.scalars(select(LineOperator).order_by(LineOperator.id)))
    assert [(r.operator_id, r.end_at is not None) for r in rows] == [(world["yamada"], True), (world["sato"], False)]


def test_operator_change_rules(client, world):
    conflict(client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": 999}), "作業者(内部の番号 999)が見つかりません")
    r = client.put("/api/lines/X/operator", json={"request_id": rid(), "operator_id": world["yamada"]})
    assert r.status_code == 404 and "ライン「X」が見つかりません" in r.json()["detail"]
    # ラインの記号は正規化して探す(s → S)
    assert client.get("/api/lines/s/operator").status_code == 200


def test_same_operator_again_does_not_add_row(client, world):
    set_operator(client, world["yamada"])
    set_operator(client, world["yamada"])
    assert count_rows(LineOperator) == 1
