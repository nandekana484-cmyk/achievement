"""管理者のルートがすべて認証を要求していること(S-14)。新しいルートを足し忘れると失敗する。詳細: docs/design/security.md

app の全ルート(OpenAPI の定義から。FastAPI 0.150 の app.routes は入れ子で数えにくい)を列挙し、/api/admin/ の下のルートを、ログインなしで(書き込みには X-Genba-Admin を付けて)呼ぶ。
ログインなしで通ってよいのは、LOGIN_FREE の2つだけ。
"""

from __future__ import annotations

import re

from admin_helpers import H

LOGIN_FREE = {("POST", "/api/admin/login"), ("POST", "/api/admin/logout")}


def _admin_routes():
    from app.main import app

    return sorted((m.upper(), path) for path, ops in app.openapi()["paths"].items() if path.startswith("/api/admin")
                  for m in ops if m.upper() not in ("HEAD", "OPTIONS"))


def test_every_admin_route_refuses_requests_without_login(client):
    routes = _admin_routes()
    assert len(routes) >= 19, routes  # 列挙できていること(空のまま通らないように)
    for method, path in routes:
        if (method, path) in LOGIN_FREE:
            continue
        url = re.sub(r"\{[^}]+\}", "1", path)
        r = client.request(method, url, headers=H, json={} if method != "GET" else None)
        assert r.status_code == 401, f"{method} {path} がログインなしで {r.status_code} を返した"


def test_login_free_routes_are_only_the_expected_ones(client):
    assert LOGIN_FREE <= set(_admin_routes())
    r = client.post("/api/admin/logout", headers=H)
    assert r.status_code == 204


def test_every_admin_write_route_needs_the_header(client, logged_in):
    for method, path in _admin_routes():
        if method == "GET":
            continue
        url = re.sub(r"\{[^}]+\}", "1", path)
        r = client.request(method, url, json={})
        assert r.status_code == 403, f"{method} {path} が X-Genba-Admin 無しで {r.status_code} を返した"
