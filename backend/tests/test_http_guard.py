"""すべての応答にセキュリティヘッダーが付くこと(S-10)。詳細: docs/design/security.md"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
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


def _limited(max_bytes: int):
    from app.http_guard import BodyLimitMiddleware

    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"n": len(await request.body())}

    return TestClient(app)


def test_body_over_the_limit_is_413_and_under_is_ok():
    c = _limited(1000)
    assert c.post("/echo", content=b"a" * 1000).json() == {"n": 1000}
    r = c.post("/echo", content=b"a" * 1001)
    assert r.status_code == 413 and "大きすぎ" in r.json()["detail"]


def test_chunked_body_without_content_length_is_counted():
    c = _limited(1000)

    def chunks():
        for _ in range(5):
            yield b"a" * 300

    assert c.post("/echo", content=chunks()).status_code == 413


def test_real_app_refuses_a_big_body_and_default_is_5mb(tmp_path, monkeypatch):
    from app.core.config import load_config

    assert load_config(tmp_path / "none.toml").server.max_body_mb == 5
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "t.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    big = b'{"request_id":"r","text":"' + b"a" * (6 * 1024 * 1024) + b'"}'
    with TestClient(app) as c:
        r = c.post("/api/runs/K1/remarks", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert r.headers["X-Frame-Options"] == "DENY"
