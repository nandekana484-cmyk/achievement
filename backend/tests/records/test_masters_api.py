"""マスタの取得、ラインの自動登録、入力の検証。"""

from sqlalchemy import select

from app.db.models import Equipment, Line, Reason
from legacy_fixture import insert_plan
from records_helpers import K1, rid, new_session, sync_plans, reason_id, start, ok


def test_masters(client, staffed, equipment):
    with new_session() as s:
        s.add(Equipment(line_code="S", name="使わない設備", active=False, sort_order=1))
        s.get(Reason, reason_id("計画切替")).active = False
        s.commit()

    m = ok(client.get("/api/masters"))
    assert [x["line_code"] for x in m["lines"]] == ["S", "T"]
    assert [x["name"] for x in m["operators"]] == ["佐藤", "山田"]  # 名前順
    assert [x["name"] for x in m["equipment"]] == ["マウンター1", "マウンター9"]  # 無効なものは出さない
    assert "計画切替" not in [x["name"] for x in m["reasons"]]
    assert m["reasons"][0]["name"] == "部品探し" and m["reasons"][0]["category"] == "loss"

    assert [x["name"] for x in ok(client.get("/api/masters", params={"line_code": "S"}))["equipment"]] == ["マウンター1"]
    assert client.get("/api/masters", params={"line_code": "X"}).status_code == 404


def test_sync_registers_new_lines(client, world):
    insert_plan(world["db"], kitting_no="0722-1-T-251014-09", line="t")
    sync_plans(world["app"])
    with new_session() as s:
        lines = {line.line_code: line.name for line in s.scalars(select(Line))}
    assert lines == {"S": "Sライン", "T": "Tライン"}


def test_requests_without_request_id_are_rejected(client, staffed):
    r = client.post(f"/api/runs/{K1}/steps/setup/start", json={})
    assert r.status_code == 422
    r = client.post(f"/api/runs/{K1}/steps/setup/start", json={"request_id": rid(), "unknown": 1})
    assert r.status_code == 422  # 知らない項目は受け付けない
