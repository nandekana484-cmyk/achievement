"""作業者IDで呼び出す(GET /api/operators/lookup)と、担当者の交代・記録者の指定での worker_id。"""

import pytest

from app.db.models import Operator
from app.services import masters
from records_helpers import conflict, new_session, ok, rid, start


@pytest.fixture
def ids(client, world):
    """world の作業者に作業者IDを付け、無効な作業者も1人足す。"""
    with new_session() as s:
        for op_id, wid in ((world["yamada"], "Y001"), (world["sato"], "S002")):
            op = s.get(Operator, op_id)
            op.worker_id, op.worker_key = wid, wid.lower()
        s.commit()
        retired = masters.add_operator(s, "退職者", worker_id="R9")
        retired.active = False
        s.commit()
    return world


def lookup(client, worker_id):
    return client.get("/api/operators/lookup", params={"worker_id": worker_id})


def test_lookup_ignores_width_and_case(client, ids):
    for q in ("Y001", "y001", "Ｙ００１", " y001 "):
        r = ok(lookup(client, q))
        assert (r["id"], r["name"], r["worker_id"]) == (ids["yamada"], "山田", "Y001")


def test_lookup_not_found(client, ids):
    for q in ("R9", "Z999", ""):  # 無効な作業者・無いID・空
        r = lookup(client, q)
        assert r.status_code == 404 and r.json()["detail"] == "作業者IDが見つかりません"


def test_change_operator_by_worker_id(client, ids):
    r = ok(client.put("/api/lines/S/operator", json={"request_id": rid(), "worker_id": "ｓ００２"}))
    assert (r["operator_id"], r["operator_name"], r["operator_worker_id"]) == (ids["sato"], "佐藤", "S002")
    r = client.put("/api/lines/S/operator", json={"request_id": rid(), "worker_id": "Z999"})
    assert r.status_code == 404
    conflict(client.put("/api/lines/S/operator", json={"request_id": rid()}), "担当者(作業者ID)を指定してください")


def test_recorder_by_worker_id(client, ids):
    e = ok(start(client, "setup", worker_id="y001"))["event"]
    assert (e["started_by"], e["started_by_name"], e["started_by_worker_id"]) == (ids["yamada"], "山田", "Y001")
    assert start(client, "n1_check", worker_id="R9").status_code == 404  # 無効な作業者
    conflict(start(client, "n1_check", worker_id="Y001", operator_id=ids["sato"]), "どちらか一方だけ")


def test_masters_list_operators_by_name_with_ids(client, ids):
    with new_session() as s:
        masters.add_operator(s, "山田", worker_id="Y015")  # 同じ名前の人
    ops = ok(client.get("/api/masters"))["operators"]
    assert [(o["name"], o["worker_id"]) for o in ops] == [("佐藤", "S002"), ("山田", "Y001"), ("山田", "Y015")]


def test_add_operator_rejects_colliding_or_long_ids(client, ids):
    with new_session() as s:
        with pytest.raises(Exception, match="ほかの作業者と重なります"):
            masters.add_operator(s, "別人", worker_id="ｙ００１")
        with pytest.raises(Exception, match="1〜32文字"):
            masters.add_operator(s, "長い", worker_id="X" * 33)
