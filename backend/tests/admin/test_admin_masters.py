"""管理画面のマスタの管理(設備・理由・ライン・作業者)と audit_log。"""

import json

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, Reason
from app.db.session import get_sessionmaker
from app.services import admin_masters, line_events
from app.services.errors import RuleViolation
from admin_helpers import H


def _audit(table):
    with get_sessionmaker()() as s:
        return [(r.action, r.target_key, json.loads(r.before_json) if r.before_json else None, json.loads(r.after_json), r.changed_by)
                for r in s.scalars(select(AuditLog).where(AuditLog.target_table == table).order_by(AuditLog.id))]


def _reason_id(name):
    with get_sessionmaker()() as s:
        return s.scalars(select(Reason).where(Reason.name == name)).one().id


def test_equipment_add_update_deactivate(client, logged_in):
    r = client.post("/api/admin/equipment", json={"line_code": "s", "name": " マウンター3 ", "name_vi": "Máy gắn 3"}, headers=H)
    assert r.status_code == 200
    eq = r.json()
    assert (eq["line_code"], eq["name"], eq["name_vi"], eq["active"]) == ("S", "マウンター3", "Máy gắn 3", True)

    r = client.patch(f"/api/admin/equipment/{eq['id']}", json={"name": "マウンター3号", "sort_order": 5}, headers=H)
    assert (r.json()["name"], r.json()["sort_order"], r.json()["name_vi"]) == ("マウンター3号", 5, "Máy gắn 3")
    assert client.patch(f"/api/admin/equipment/{eq['id']}", json={"active": False}, headers=H).json()["active"] is False
    assert client.patch(f"/api/admin/equipment/{eq['id']}", json={"active": False}, headers=H).status_code == 200  # 変わらない

    assert [x["name"] for x in client.get("/api/admin/equipment").json()] == ["マウンター3号"]  # 無効なものも一覧に出る
    assert client.get("/api/masters", params={"line_code": "S"}).json()["equipment"] == []  # 現場の画面には出ない
    admin = logged_in["admin"]
    assert _audit("equipment") == [
        ("create", str(eq["id"]), None, {"line_code": "S", "name": "マウンター3", "name_vi": "Máy gắn 3", "sort_order": 10, "active": True}, admin),
        ("update", str(eq["id"]), {"name": "マウンター3", "sort_order": 10}, {"name": "マウンター3号", "sort_order": 5}, admin),
        ("update", str(eq["id"]), {"active": True}, {"active": False}, admin),
    ]  # 変わらなかった変更は残さない


def test_equipment_needs_a_registered_line_and_a_name(client, logged_in):
    assert client.post("/api/admin/equipment", json={"line_code": "X", "name": "a"}, headers=H).status_code == 409
    r = client.post("/api/admin/equipment", json={"line_code": "S", "name": "a"}, headers=H).json()
    assert client.patch(f"/api/admin/equipment/{r['id']}", json={"name": "  "}, headers=H).json()["detail"] == "名前が空です"
    assert client.patch("/api/admin/equipment/999", json={"name": "b"}, headers=H).status_code == 404


def test_reason_add_and_update_every_field(client, logged_in):
    r = client.post("/api/admin/reasons", json={"name": "清掃", "category": "non_loss", "usable_as_line_event": True}, headers=H)
    new = r.json()
    assert (new["category"], new["usable_as_line_event"], new["usable_as_restart"], new["active"]) == ("non_loss", True, False, True)
    changes = {"name": "清掃・点検", "name_vi": "Vệ sinh", "category": "loss", "requires_equipment": True, "requires_text": True,
               "usable_as_restart": True, "counts_in_utilization": True, "sort_order": 1}
    after = client.patch(f"/api/admin/reasons/{new['id']}", json=changes, headers=H).json()
    assert {k: after[k] for k in changes} == changes
    assert client.patch(f"/api/admin/reasons/{new['id']}", json={"category": "other"}, headers=H).status_code == 409
    assert [a[0] for a in _audit("reasons")] == ["create", "update"]
    assert _audit("reasons")[1][2]["name"] == "清掃"


def test_line_rename_drops_the_automatic_name(client, logged_in):
    assert client.get("/api/admin/lines").json()[0]["auto_named"] is True
    r = client.patch("/api/admin/lines/s", json={"name": "第1実装ライン", "sort_order": 3}, headers=H).json()
    assert (r["name"], r["auto_named"], r["sort_order"]) == ("第1実装ライン", False, 3)
    assert client.get("/api/masters").json()["lines"][0]["auto_named"] is False
    client.patch("/api/admin/lines/S", json={"active": False}, headers=H)
    assert client.get("/api/masters").json()["lines"] == []
    assert _audit("lines")[0][2:4] == ({"name": "Sライン", "sort_order": 10}, {"name": "第1実装ライン", "sort_order": 3})


def test_operators_are_read_only_except_local_ones(client, logged_in):
    ops = {o["worker_id"]: o for o in client.get("/api/admin/operators").json()}
    assert (ops["K0042"]["role"], ops["K0042"]["has_password"], ops["Y001"]["has_password"]) == ("admin", True, False)
    r = client.post("/api/admin/operators", json={"name": "開発用", "worker_id": "D9"}, headers=H)
    assert r.status_code == 200 and r.json()["source"] == "local"  # legacy_app_dir が無い環境だけ
    with get_sessionmaker()() as s, pytest.raises(RuleViolation, match="既存アプリから読み込む"):
        admin_masters.add_local_operator(s, logged_in["admin"], "x", None, legacy_app_dir_set=True)
    assert [a[0] for a in _audit("operators")] == ["create"]


def test_deactivating_a_used_reason_keeps_past_records(client, logged_in):
    trouble = _reason_id("部品探し")
    with get_sessionmaker()() as s:
        ev = line_events.start_line_event(s, "S", trouble, "req-1", operator_id=logged_in["worker"])
    assert client.patch(f"/api/admin/reasons/{trouble}", json={"active": False}, headers=H).status_code == 200

    board = client.get("/api/lines/S/board", params={"date": "2026-10-21"}).json()
    [shown] = [e for e in board["line_events"] if e["id"] == ev.id]
    assert (shown["reason_name"], shown["reason_name_vi"]) == ("部品探し", "Tìm linh kiện")  # 過去の記録の表示は変わらない
    assert "部品探し" not in [r["name"] for r in client.get("/api/masters").json()["reasons"]]  # 新しくは選べない
