"""アクセス制限(登録したIPアドレスだけ許す)。詳細: docs/design/security.md(アクセス制限)"""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import select

from admin_helpers import PASSWORD, H, login
from app.db.models import AllowedNetwork, AuditLog
from app.db.session import get_sessionmaker
from app.ip_access import DENIED_MESSAGE
from app.services import ip_allowlist


def at(ip: str) -> TestClient:
    """この接続元(TCP の相手)から来る client。"""
    from app.main import app

    return TestClient(app, client=(ip, 40000))


def add(network: str, scope: str = "field", actor: int | None = None, note: str | None = None):
    with get_sessionmaker()() as s:
        return ip_allowlist.add_network(s, actor, network, scope, note)


def rows():
    with get_sessionmaker()() as s:
        return list(s.scalars(select(AllowedNetwork).order_by(AllowedNetwork.id)))


def health_ok(ip: str) -> bool:
    return at(ip).get("/api/health").status_code == 200


# --- 判定 ---

def test_no_rules_means_no_restriction(client, people):
    for host in ("10.9.9.9", "testclient", "::1"):
        assert health_ok(host)


def test_denied_gets_403_with_a_short_japanese_page_or_json(client, people):
    add("192.168.3.0/24")
    page = at("10.0.0.9").get("/field")
    assert page.status_code == 403 and DENIED_MESSAGE in page.text and "10.0.0.9" in page.text
    assert page.headers["content-type"].startswith("text/html") and page.headers["x-frame-options"] == "DENY"
    api = at("10.0.0.9").get("/api/health")
    assert api.status_code == 403 and api.json() == {"detail": DENIED_MESSAGE}
    assert health_ok("192.168.3.77")


def test_every_kind_of_path_is_covered(client, people):
    add("192.168.3.0/24")
    denied = at("10.0.0.9")
    for path in ("/", "/field", "/assets/x.js", "/favicon.svg", "/api/masters", "/api/lines/S/board", "/admin", "/admin/login",
                 "/api/admin/me", "/no/such/page", "/..%2fdata%2fconfig.toml"):
        assert denied.get(path).status_code == 403, path
    assert denied.post("/api/admin/login", json={"worker_id": "K0042", "password": PASSWORD}, headers=H).status_code == 403


def test_cidr_edges_and_single_ip(client, people):
    add("192.168.3.0/24")
    add("172.16.5.9")
    assert health_ok("192.168.3.0") and health_ok("192.168.3.255")
    assert not health_ok("192.168.2.255") and not health_ok("192.168.4.0")
    assert health_ok("172.16.5.9") and not health_ok("172.16.5.8") and not health_ok("172.16.5.10")


def test_ipv6_and_ipv4_mapped(client, people):
    add("fd00:1::/64")
    add("192.168.3.0/24")
    assert health_ok("fd00:1::abcd") and not health_ok("fd00:2::1") and not health_ok("fe80::1")
    assert health_ok("::ffff:192.168.3.5") and not health_ok("::ffff:10.0.0.5")  # 射影は IPv4 として判定する
    assert health_ok("::1") and health_ok("127.0.0.1") and health_ok("::ffff:127.0.0.1")  # サーバーのPC自身は常に許可


def test_loopback_is_always_allowed_even_to_the_admin_screen(client, people):
    add("192.168.3.0/24", "field")
    add("192.168.9.5", "admin")
    for host in ("127.0.0.1", "::1"):
        assert at(host).get("/api/admin/me").status_code == 401  # 403 ではなく、ログインを求める(通っている)


def test_forwarding_headers_are_ignored(client, people):
    add("192.168.3.0/24")
    spoof = {"X-Forwarded-For": "192.168.3.5", "X-Real-IP": "192.168.3.5", "Forwarded": "for=192.168.3.5", "X-Forwarded-Host": "localhost",
             "Client-IP": "127.0.0.1", "True-Client-IP": "127.0.0.1", "X-Originating-IP": "127.0.0.1"}
    assert at("10.0.0.9").get("/api/health", headers=spoof).status_code == 403  # 偽装しても許可されない
    assert at("192.168.3.5").get("/api/health", headers={"X-Forwarded-For": "10.0.0.9"}).status_code == 200  # 許可された相手は偽装の影響を受けない


def test_unreadable_peer_is_denied_when_restricted(client, people):
    add("192.168.3.0/24")
    assert not health_ok("testclient")


def test_admin_list_empty_follows_the_field_list(client, people):
    add("192.168.3.0/24")
    assert at("192.168.3.5").get("/api/admin/me").status_code == 401  # 通っている(ログインが要る)
    assert at("10.0.0.9").get("/api/admin/me").status_code == 403


def test_admin_list_limits_the_admin_screen_only(client, people):
    add("192.168.3.0/24", "field")
    add("192.168.9.5", "admin")
    tablet, pc = at("192.168.3.5"), at("192.168.9.5")
    assert tablet.get("/api/health").status_code == 200
    for path in ("/api/admin/me", "/admin/login", "/admin"):
        assert tablet.get(path).status_code == 403, path
    assert tablet.post("/api/admin/login", json={"worker_id": "K0042", "password": PASSWORD}, headers=H).status_code == 403
    assert pc.get("/api/admin/me").status_code == 401
    assert login(pc).status_code == 200
    assert pc.get("/api/health").status_code == 200  # 管理画面用の接続元は現場の画面も使える


def test_admin_list_alone_leaves_the_field_open(client, people):
    add("192.168.9.5", "admin")
    assert health_ok("10.0.0.9")
    assert at("10.0.0.9").get("/api/admin/me").status_code == 403


def test_disabling_everything_lifts_the_restriction(client, people):
    r = add("192.168.3.0/24")
    assert not health_ok("10.0.0.9")
    with get_sessionmaker()() as s:
        ip_allowlist.disable_network(s, None, r.id)
    assert health_ok("10.0.0.9")


def test_changes_by_another_process_show_up_after_the_cache_time(client, people, monkeypatch):
    add("192.168.3.0/24")
    assert not health_ok("10.0.0.9")
    with get_sessionmaker()() as s:  # 開発用コマンド(別のプロセス)の変更を真似る: 覚えを消さずにDBだけ変える
        s.get(AllowedNetwork, rows()[0].id).active = False
        s.commit()
    assert not health_ok("10.0.0.9")  # まだ覚えている
    monkeypatch.setattr(ip_allowlist, "CACHE_SECONDS", 0.0)
    assert health_ok("10.0.0.9")


# --- 登録・無効化の API ---

def test_requires_login_and_header(client, people):
    assert client.get("/api/admin/access", headers=H).status_code == 401
    body = {"network": "10.0.0.1", "scope": "field"}
    assert client.post("/api/admin/access/networks", json=body, headers=H).status_code == 401
    assert client.post("/api/admin/access/networks/1/disable", headers=H).status_code == 401
    assert login(client).status_code == 200
    assert client.post("/api/admin/access/networks", json=body).status_code == 403  # ヘッダーなし


def test_status_shows_my_ip_and_whether_it_is_allowed(client, people):
    pc = at("192.168.3.5")
    assert login(pc).status_code == 200
    s = pc.get("/api/admin/access").json()
    assert s["my_ip"] == "192.168.3.5" and not s["field_restricted"] and s["field_allowed"] and s["admin_allowed"] and s["networks"] == []
    body = {"network": "192.168.3.0/24", "scope": "field", "note": "タブレット"}
    assert pc.post("/api/admin/access/networks", json=body, headers=H).status_code == 200
    s = pc.get("/api/admin/access").json()
    assert s["field_restricted"] and not s["admin_restricted"] and s["admin_allowed"]
    assert [(n["network"], n["scope"], n["note"], n["active"], n["created_by"]) for n in s["networks"]] == [
        ("192.168.3.0/24", "field", "タブレット", True, "管理 花子(K0042)")]


def test_ipv4_mapped_client_is_shown_and_treated_as_ipv4(client, people):
    pc = at("::ffff:192.168.3.5")
    assert login(pc).status_code == 200
    assert pc.get("/api/admin/access").json()["my_ip"] == "192.168.3.5"


def test_loopback_admin_can_change_anything(client, people):
    pc = at("127.0.0.1")
    assert login(pc).status_code == 200
    assert pc.post("/api/admin/access/networks", json={"network": "192.168.3.0/24", "scope": "field"}, headers=H).status_code == 200
    assert pc.post("/api/admin/access/networks", json={"network": "192.168.9.9", "scope": "admin"}, headers=H).status_code == 200
    assert pc.get("/api/admin/access").json()["my_ip_is_loopback"] is True


def test_cannot_lock_out_my_own_ip(client, people):
    add("192.168.3.0/24")
    add("172.16.0.0/16")
    pc = at("192.168.3.5")
    assert login(pc).status_code == 200
    # 管理画面用の一覧を作ると、今の接続元が入っていなければ外れる
    r = pc.post("/api/admin/access/networks", json={"network": "10.0.0.0/8", "scope": "admin"}, headers=H)
    assert r.status_code == 409 and "192.168.3.5" in r.json()["detail"] and "許可されなくなり" in r.json()["detail"]
    assert pc.post("/api/admin/access/networks", json={"network": "192.168.3.0/28", "scope": "admin"}, headers=H).status_code == 200
    # 管理画面用を無効にすると、現場用の 192.168.3.0/24 に戻る → 今の接続元は残るので無効にできる
    admin_row = next(r for r in rows() if r.scope == "admin")
    assert pc.post(f"/api/admin/access/networks/{admin_row.id}/disable", headers=H).status_code == 200
    # 今の接続元を許している範囲は、ほかに許す範囲が無ければ無効にできない(172.16.0.0/16 は今の接続元を含まない)
    own = next(r for r in rows() if r.scope == "field" and r.network == "192.168.3.0/24")
    r = pc.post(f"/api/admin/access/networks/{own.id}/disable", headers=H)
    assert r.status_code == 409 and "別の範囲を、先に登録" in r.json()["detail"]
    assert next(row for row in rows() if row.id == own.id).active
    other = next(r for r in rows() if r.network == "172.16.0.0/16")
    assert pc.post(f"/api/admin/access/networks/{other.id}/disable", headers=H).status_code == 200  # 自分が残るなら無効にできる


def test_first_restriction_must_include_my_ip(client, people):
    pc = at("192.168.3.5")
    assert login(pc).status_code == 200
    r = pc.post("/api/admin/access/networks", json={"network": "10.0.0.0/8", "scope": "field"}, headers=H)
    assert r.status_code == 409 and rows() == []  # 制限をかけると今の接続元が外れる
    assert pc.post("/api/admin/access/networks", json={"network": "192.168.3.5", "scope": "field"}, headers=H).status_code == 200
    assert pc.post("/api/admin/access/networks", json={"network": "10.0.0.0/8", "scope": "field"}, headers=H).status_code == 200


def test_disabling_the_last_range_is_allowed_because_the_restriction_ends(client, people):
    only = add("192.168.3.0/24")
    pc = at("192.168.3.5")
    assert login(pc).status_code == 200
    assert pc.post(f"/api/admin/access/networks/{only.id}/disable", headers=H).status_code == 200
    assert health_ok("10.0.0.9")


def test_validation_messages(client, people):
    pc = at("127.0.0.1")
    assert login(pc).status_code == 200

    def post(**b):
        return pc.post("/api/admin/access/networks", json=b, headers=H)

    assert "書き方が正しくありません" in post(network="abc", scope="field").json()["detail"]
    assert "/0" in post(network="0.0.0.0/0", scope="field").json()["detail"]
    assert post(network="10.0.0.0/8", scope="bad").status_code == 422
    assert post(network="10.0.0.0/8", scope="field").status_code == 200
    r = post(network="10.0.0.5/8", scope="field")  # 同じ範囲(書き方が違っても)
    assert r.status_code == 409 and "すでに登録されています" in r.json()["detail"]
    assert post(network="10.0.0.0/8", scope="admin").status_code == 200  # 区分が違えば別
    assert pc.post("/api/admin/access/networks/999/disable", headers=H).status_code == 404


def test_history_is_kept_and_audited(client, people):
    pc = at("127.0.0.1")
    assert login(pc).status_code == 200
    n = pc.post("/api/admin/access/networks", json={"network": "10.0.0.0/8", "scope": "field", "note": "本社"}, headers=H).json()
    assert pc.post(f"/api/admin/access/networks/{n['id']}/disable", headers=H).json()["active"] is False
    assert pc.post(f"/api/admin/access/networks/{n['id']}/disable", headers=H).status_code == 200  # 2回目も同じ結果
    listed = pc.get("/api/admin/access").json()["networks"]
    assert [(x["network"], x["active"], x["disabled_by"]) for x in listed] == [("10.0.0.0/8", False, "管理 花子(K0042)")]
    assert listed[0]["disabled_at"]
    with get_sessionmaker()() as s:
        log = s.scalars(select(AuditLog).where(AuditLog.target_table == "allowed_networks")).all()
        assert [a.action for a in log] == ["create", "update"]
    assert len(rows()) == 1  # 行は消えない


# --- 拒否の記録、起動のログ ---

def test_denials_are_logged_once_per_minute_per_ip(client, people, caplog):
    add("192.168.3.0/24")
    with caplog.at_level(logging.WARNING, logger="app.ip_access"):
        for _ in range(5):
            at("10.0.0.9").get("/api/masters")
        at("10.0.0.10").get("/field")
    lines = [r.getMessage() for r in caplog.records if "アクセス制限で拒否" in r.getMessage()]
    assert len(lines) == 2  # 10.0.0.9 は1回、10.0.0.10 は1回
    assert "10.0.0.9" in lines[0] and "/api/masters" in lines[0] and "10.0.0.10" in lines[1] and "/field" in lines[1]


def test_deny_log_summarises_the_skipped_ones_after_the_interval(caplog):
    from app.ip_access import DenyLog

    log = DenyLog(interval=0.0)
    log._last["1.1.1.1"] = 0.0  # noqa: SLF001
    log._skipped["1.1.1.1"] = 3  # noqa: SLF001
    with caplog.at_level(logging.WARNING, logger="app.ip_access"):
        log.record("1.1.1.1", "/x")
    assert "ほかに3回" in caplog.text


def test_startup_log_says_whether_the_restriction_is_on(client, people, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.ip_allowlist"):
        ip_allowlist.log_access_restriction()
        add("192.168.3.0/24")
        add("192.168.9.5", "admin")
        add("192.168.9.6", "admin")
        ip_allowlist.log_access_restriction()
    msgs = [r.getMessage() for r in caplog.records]
    assert any("無効" in m for m in msgs)
    assert any("有効" in m and "現場用 1件" in m and "管理画面用 2件" in m for m in msgs)


# --- ログイン失敗の制限(接続元ごと)との組み合わせ ---

def test_login_lockout_works_for_allowed_ips_and_denied_ips_never_reach_it(client, people):
    add("192.168.3.0/24")
    allowed, denied = at("192.168.3.5"), at("10.0.0.9")
    for i in range(25):  # 許可されていない接続元は 403 で止まり、失敗として数えない
        r = denied.post("/api/admin/login", json={"worker_id": f"N{i}", "password": "wrong-pass-1"}, headers=H)
        assert r.status_code == 403
    assert login(allowed).status_code == 200  # 影響を受けない
    for i in range(20):
        assert login(allowed, worker_id=f"NOBODY{i}", password="wrong-pass-1").status_code == 401
    r = login(allowed)
    assert r.status_code == 429 and "この端末" in r.json()["detail"]  # 許可された接続元には、5分で20回の制限が働く
    assert login(at("192.168.3.6")).status_code == 200  # 同じ範囲の別の接続元は別に数える


def test_mapped_and_plain_forms_of_one_ip_share_the_failure_count(client, people):
    add("192.168.3.0/24")
    plain, mapped = at("192.168.3.5"), at("::ffff:192.168.3.5")
    for i in range(10):
        login(plain, worker_id=f"A{i}", password="wrong-pass-1")
    for i in range(10):
        login(mapped, worker_id=f"B{i}", password="wrong-pass-1")
    assert login(plain).status_code == 429 and login(mapped).status_code == 429


def test_lockout_by_ip_does_not_block_the_server_pc_itself(client, people):
    add("192.168.3.0/24")
    for i in range(20):
        login(at("192.168.3.5"), worker_id=f"N{i}", password="wrong-pass-1")
    assert login(at("192.168.3.5")).status_code == 429
    assert login(at("127.0.0.1")).status_code == 200  # サーバーのPC自身は別の接続元


# --- 一覧を読めないとき ---

def _break_db(monkeypatch):
    def boom():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(ip_allowlist, "get_sessionmaker", boom)


def test_first_load_failure_fails_closed_except_for_the_server_pc(client, people, monkeypatch, caplog):
    """一覧を一度も読めていないときは、制限する側に倒す(127.0.0.1 と ::1 以外は 403)。ログに理由を残す。"""
    real = ip_allowlist.get_sessionmaker
    ip_allowlist.cache.reset()
    _break_db(monkeypatch)
    with caplog.at_level(logging.ERROR, logger="app.services.ip_allowlist"):
        assert at("10.0.0.9").get("/api/health").status_code == 403
        assert at("192.168.3.5").get("/field").status_code == 403
        assert at("192.168.3.5").get("/api/admin/me").status_code == 403
        assert at("127.0.0.1").get("/api/health").status_code == 200
        assert at("::1").get("/api/health").status_code == 200
    assert "まだ一度も読めていません" in caplog.text and "database is locked" in caplog.text  # 理由(例外)もログに出る
    monkeypatch.setattr(ip_allowlist, "get_sessionmaker", real)  # 読めるようになったら、1秒以内に元に戻る
    ip_allowlist.cache._loaded_at = 0.0  # noqa: SLF001
    assert health_ok("10.0.0.9")


def test_failure_after_a_good_load_keeps_using_the_previous_lists(client, people, monkeypatch, caplog):
    add("192.168.3.0/24")
    assert health_ok("192.168.3.5") and not health_ok("10.0.0.9")  # 読めた(覚えた)
    _break_db(monkeypatch)
    ip_allowlist.cache.invalidate()  # 覚えが古くなって、読み直しに失敗する
    with caplog.at_level(logging.ERROR, logger="app.services.ip_allowlist"):
        assert health_ok("192.168.3.5") and not health_ok("10.0.0.9")  # 前の一覧のまま
        assert health_ok("127.0.0.1")
    assert "前に読んだ一覧を使います" in caplog.text and "database is locked" in caplog.text


def test_unrestricted_state_stays_unrestricted_when_a_later_load_fails(client, people, monkeypatch):
    assert health_ok("10.0.0.9")  # 制限なしで読めた
    _break_db(monkeypatch)
    ip_allowlist.cache.invalidate()
    assert health_ok("10.0.0.9")  # 読めた結果が「制限なし」だったので、一時的な失敗では締め出さない


def test_startup_log_reports_unreadable_lists(client, people, monkeypatch, caplog):
    ip_allowlist.cache.reset()
    _break_db(monkeypatch)
    with caplog.at_level(logging.ERROR, logger="app.services.ip_allowlist"):
        ip_allowlist.log_access_restriction()
    assert "一覧を読めません" in caplog.text
