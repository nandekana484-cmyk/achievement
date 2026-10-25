"""本番は /docs・/redoc・/openapi.json を開かない(S-02)。設定 [server] expose_docs で開ける。詳細: docs/design/security.md"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import load_config
from app.main import docs_urls


def test_docs_are_off_by_default(tmp_path):
    assert load_config(tmp_path / "none.toml").server.expose_docs is False
    client = TestClient(FastAPI(**docs_urls(False)))
    for url in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(url).status_code == 404, url


def test_docs_can_be_turned_on(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[server]\nexpose_docs = true\n", encoding="utf-8")
    assert load_config(p).server.expose_docs is True
    client = TestClient(FastAPI(**docs_urls(True)))
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_openapi_export_works_without_exposing_docs():
    from app.main import app

    assert app.openapi()["paths"]
