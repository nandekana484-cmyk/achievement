from fastapi.testclient import TestClient


def test_health(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "t.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))

    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db_journal_mode"] == "wal"
    assert body["server_time"].endswith("+09:00")
