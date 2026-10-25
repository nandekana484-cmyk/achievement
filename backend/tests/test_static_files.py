"""画面の配信: 配信フォルダの外のファイルを返さないこと(S-01)と、画面の遷移・API の 404(S-15)。詳細: docs/design/security.md"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.static_files import mount_spa, resolve_static_file

SECRET = "SECRET-CONFIG"


@pytest.fixture
def site(tmp_path):
    """tmp/dist(配信フォルダ)と、その外の tmp/data/config.toml(読まれてはいけないファイル)。"""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>INDEX</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "config.toml").write_text(SECRET, encoding="utf-8")
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    app = FastAPI()
    mount_spa(app, dist)
    return tmp_path, TestClient(app)


ATTACKS = [
    "/..%2fdata%2fconfig.toml",
    "/..%2fsecret.txt",
    "/%2e%2e/data/config.toml",
    "/%2e%2e%2fdata%2fconfig.toml",
    "/..%5cdata%5cconfig.toml",
    r"/..\data\config.toml",
    "/%252e%252e/data/config.toml",
    "/..%252fdata%252fconfig.toml",
    "/%2e%2e%5cdata%5cconfig.toml",
    "/%2fdata%2fconfig.toml",
    "/C:/Windows/win.ini",
    "/C%3a%5cWindows%5cwin.ini",
    "/config.toml%00.html",
    "/..%00/data/config.toml",
    "/.. /data/config.toml",
    "/...%2fdata%2fconfig.toml",
    "/assets/..%2f..%2fdata%2fconfig.toml",
    "/assets/%2e%2e/%2e%2e/data/config.toml",
    "/assets/..%2fapp.js",
]


@pytest.mark.parametrize("url", ATTACKS)
def test_attacks_are_refused_and_never_leak(site, url):
    _, client = site
    r = client.get(url)
    assert SECRET not in r.text
    assert r.status_code == 404, url


def test_double_slash_prefix_never_leaks(site):
    _, client = site
    assert SECRET not in client.get("//data/config.toml").text


@pytest.mark.parametrize("path", [
    "../data/config.toml", "../secret.txt", "..", "a/../../secret.txt", "/etc/passwd", "C:/x", r"..\secret.txt", "x\0", "%2e%2e/secret.txt",
])
def test_resolve_refuses_unsafe_paths(site, path):
    tmp, _ = site
    with pytest.raises(HTTPException) as e:
        resolve_static_file(tmp / "dist", path)
    assert e.value.status_code == 404


def test_resolve_refuses_a_symlink_out_of_the_folder(site):
    tmp, _ = site
    link = tmp / "dist" / "link.txt"
    try:
        link.symlink_to(tmp / "secret.txt")
    except OSError:
        pytest.skip("シンボリックリンクを作れない環境")
    with pytest.raises(HTTPException):
        resolve_static_file(tmp / "dist", "link.txt")


def test_normal_files_and_screen_routes_still_work(site):
    _, client = site
    assert "INDEX" in client.get("/").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    for route in ("/field/S", "/admin/login", "/admin/equipment", "/nothing/here", "/a.b"):
        r = client.get(route)
        assert r.status_code == 200 and "INDEX" in r.text, route


def test_unknown_api_paths_are_json_404(site):
    _, client = site
    for url in ("/api/nothing", "/api", "/api/admin/nothing", "/api/%2e%2e/x"):
        r = client.get(url)
        assert r.status_code == 404, url
        assert r.headers["content-type"].startswith("application/json")
        assert "detail" in r.json()


def test_real_app_still_serves_api_and_404s_unknown_api(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "t.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        r = client.get("/api/nothing")
        assert r.status_code in (404,) and r.headers["content-type"].startswith("application/json")
