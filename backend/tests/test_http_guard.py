"""すべての応答にセキュリティヘッダーが付くこと(S-10)。詳細: docs/design/security.md"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.http_guard import SECURITY_HEADERS, SecurityHeadersMiddleware


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ok")
    def ok() -> dict:
        return {"ok": True}

    return TestClient(app)


def test_headers_on_success_and_404(client):
    for url in ("/ok", "/missing"):
        r = client.get(url)
        for name, value in SECURITY_HEADERS.items():
            assert r.headers[name] == value, (url, name)
    assert SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
    assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"
    assert SECURITY_HEADERS["Referrer-Policy"] == "same-origin"
    assert SECURITY_HEADERS["Content-Security-Policy"] == "frame-ancestors 'none'"


def test_real_app_sends_the_headers(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "t.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/health")
    assert r.headers["X-Frame-Options"] == "DENY"
