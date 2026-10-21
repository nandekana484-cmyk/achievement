import time

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_sessionmaker
from app.services.plan_sync import run_plan_sync
from legacy_fixture import deactivate, insert_plan


def _client(tmp_path, monkeypatch, legacy_app=None, interval=60) -> TestClient:
    lines = ["[paths]", f'database = "{(tmp_path / "api.db").as_posix()}"']
    if legacy_app is not None:
        lines.append(f'legacy_app_dir = "{legacy_app.as_posix()}"')
    lines += ["[sync]", f"plan_interval_sec = {interval}"]
    cfg = tmp_path / "config.toml"
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))

    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    return TestClient(app)


@pytest.fixture
def client(tmp_path, monkeypatch, fake_clock):
    with _client(tmp_path, monkeypatch) as c:  # legacy_app_dir が未設定 → 定期同期は動かない
        yield c


def _sync(legacy_app):
    with get_sessionmaker()() as s:
        return run_plan_sync(s, legacy_app)


def test_line_plans_filtered_by_date_and_sorted(client, legacy_app, legacy_db):
    def plan(kno, start, end, **kw):
        insert_plan(legacy_db, kitting_no=kno, start=start, end=end, **kw)

    plan("0722-1-S-251014-01", "2026/10/21 13:00:00", "2026/10/21 15:00:00")
    plan("0800-1-S-251014-02", "2026/10/21 09:00:00", "2026/10/21 12:00:00")
    plan("0900-1-S-251014-03", "2026/10/20 22:00:00", "2026/10/21 01:00:00")  # 前日から続く
    plan("0901-1-S-251014-04", "2026/10/22 09:00:00", "2026/10/22 12:00:00")  # 翌日
    plan("0902-1-S-251014-05", "2026/10/20 20:00:00", "2026/10/21 00:00:00")  # 0時ちょうどに終わる
    plan("0903-1-S-251014-06", "", "")  # 日程が空
    plan("0904-1-T-251014-07", "2026/10/21 10:00:00", "2026/10/21 11:00:00", line="T")  # 別のライン
    plan("0905-1-S-251014-08", "2026/10/21 10:00:00", "2026/10/21 11:00:00")  # 取消にする
    _sync(legacy_app)
    deactivate(legacy_db, "0905-1-S-251014-08")
    _sync(legacy_app)

    r = client.get("/api/lines/S/plans", params={"date": "2026-10-21"})

    assert r.status_code == 200
    body = r.json()
    assert [p["kitting_no"] for p in body] == [
        "0900-1-S-251014-03",
        "0800-1-S-251014-02",
        "0722-1-S-251014-01",
    ]
    first = body[1]
    assert first["planned_start"] == "2026-10-21T09:00:00+09:00"
    assert first["planned_end"] == "2026-10-21T12:00:00+09:00"
    assert first["issue_date"] == "2025-10-14" and first["status"] == "active"
    assert first["source_db"] == "2026-10" and first["takt_sec"] == 30.0  # ファイルNo. 0722・S・1回目

    # date を省略すると今日(clock.now() = 2026-10-21)
    assert client.get("/api/lines/S/plans").json() == body
    assert [p["kitting_no"] for p in client.get("/api/lines/T/plans").json()] == ["0904-1-T-251014-07"]


def test_line_plans_rejects_bad_date(client):
    assert client.get("/api/lines/S/plans", params={"date": "2026/10/21"}).status_code == 422


def test_sync_status(client, legacy_app, legacy_db, tmp_path):
    assert client.get("/api/sync/status").json() == {"last_run": None, "warning_count": 0}

    insert_plan(legacy_db, kitting_no="BROKEN")
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    _sync(legacy_app)
    body = client.get("/api/sync/status").json()
    assert body["warning_count"] == 1
    assert body["last_run"]["result"] == "ok" and body["last_run"]["added"] == 1
    assert body["last_run"]["started_at"].endswith("+09:00")
    [read] = body["last_run"]["legacy_dbs"]["read"]
    assert (read["name"], read["plans"], read["adopted_plans"]) == ("2026-10", 1, 1)
    assert body["last_run"]["legacy_dbs"]["skipped"] == []

    _sync(tmp_path / "nothing")
    body = client.get("/api/sync/status").json()
    assert body["last_run"]["result"] == "error"
    assert "master.db を読めません" in body["last_run"]["error_message"]
    assert body["last_run"]["legacy_dbs"] is None
    assert body["warning_count"] == 1  # 読めなかった回は警告を変えない

    deactivate(legacy_db, "BROKEN")  # 警告の元が直った
    _sync(legacy_app)
    assert client.get("/api/sync/status").json()["warning_count"] == 0


def test_scheduler_runs_on_startup(tmp_path, monkeypatch, legacy_app, legacy_db):
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")

    with _client(tmp_path, monkeypatch, legacy_app=legacy_app) as c:
        deadline = time.monotonic() + 10
        while (body := c.get("/api/sync/status").json())["last_run"] is None:
            assert time.monotonic() < deadline, "同期が実行されませんでした"
            time.sleep(0.05)

    assert body["last_run"]["result"] == "ok" and body["last_run"]["added"] == 1
