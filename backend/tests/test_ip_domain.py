"""IPアドレスと範囲の扱い、許可の判定(純粋な部分)。詳細: docs/design/security.md(アクセス制限)"""

from __future__ import annotations

import pytest

from app.domain.networks import AccessLists, is_allowed, is_loopback, parse_ip, parse_network, scope_of_path


def test_parse_ip_handles_mapped_zone_and_garbage():
    assert str(parse_ip("192.168.3.5")) == "192.168.3.5"
    assert str(parse_ip("::ffff:192.168.3.5")) == "192.168.3.5"  # IPv4 射影は IPv4
    assert str(parse_ip("fe80::1%eth0")) == "fe80::1"  # ゾーンは外す
    assert str(parse_ip(" fd00::1 ")) == "fd00::1"
    for bad in (None, "", "testclient", "999.1.1.1", "192.168.3", "unix:/tmp/x"):
        assert parse_ip(bad) is None, bad


@pytest.mark.parametrize("text,expected", [
    ("192.168.3.5", "192.168.3.5/32"),
    ("192.168.3.0/24", "192.168.3.0/24"),
    ("192.168.3.77/24", "192.168.3.0/24"),  # ホスト部があれば範囲に直す
    ("::ffff:192.168.3.5", "192.168.3.5/32"),
    ("::ffff:192.168.3.0/120", "192.168.3.0/24"),
    ("fd00::/64", "fd00::/64"),
    ("fd00::1", "fd00::1/128"),
    ("  10.0.0.0/8 ", "10.0.0.0/8"),
])
def test_parse_network(text, expected):
    assert str(parse_network(text)) == expected


@pytest.mark.parametrize("text", ["", "abc", "192.168.3.0/33", "192.168.3.0/24/1", "192.168.3.0/x", "0.0.0.0/0", "::/0", "::ffff:0:0/96"])
def test_parse_network_refuses(text):
    with pytest.raises(ValueError):
        parse_network(text)


def _lists(field=(), admin=()):
    return AccessLists(tuple(parse_network(n) for n in field), tuple(parse_network(n) for n in admin))


def test_empty_lists_allow_everything():
    for scope in ("field", "admin"):
        assert is_allowed(_lists(), parse_ip("10.1.2.3"), scope)
        assert is_allowed(_lists(), None, scope)  # 読めない接続元も(制限していないので)


def test_field_list_restricts_field_and_admin():
    lists = _lists(field=["192.168.3.0/24"])
    assert is_allowed(lists, parse_ip("192.168.3.9"), "field") and is_allowed(lists, parse_ip("192.168.3.9"), "admin")
    assert not is_allowed(lists, parse_ip("192.168.4.9"), "field") and not is_allowed(lists, parse_ip("192.168.4.9"), "admin")
    assert not is_allowed(lists, None, "field")


def test_admin_list_narrows_admin_only_and_admin_ips_also_use_the_field():
    lists = _lists(field=["192.168.3.0/24"], admin=["192.168.9.5"])
    assert is_allowed(lists, parse_ip("192.168.3.9"), "field") and not is_allowed(lists, parse_ip("192.168.3.9"), "admin")
    assert is_allowed(lists, parse_ip("192.168.9.5"), "admin") and is_allowed(lists, parse_ip("192.168.9.5"), "field")
    assert not is_allowed(lists, parse_ip("192.168.9.6"), "field")


def test_admin_list_alone_leaves_the_field_open():
    lists = _lists(admin=["192.168.9.5"])
    assert is_allowed(lists, parse_ip("10.0.0.1"), "field") and not is_allowed(lists, parse_ip("10.0.0.1"), "admin")


def test_loopback_is_always_allowed():
    lists = _lists(field=["192.168.3.0/24"], admin=["192.168.9.5"])
    for host in ("127.0.0.1", "127.5.5.5", "::1", "::ffff:127.0.0.1"):
        assert is_loopback(parse_ip(host)) and is_allowed(lists, parse_ip(host), "admin"), host


def test_versions_do_not_mix():
    lists = _lists(field=["fd00::/8", "10.0.0.0/8"])
    assert is_allowed(lists, parse_ip("fd12::1"), "field") and is_allowed(lists, parse_ip("::ffff:10.1.1.1"), "field")
    assert not is_allowed(lists, parse_ip("fe80::1"), "field")


@pytest.mark.parametrize("path,scope", [
    ("/admin", "admin"), ("/admin/login", "admin"), ("/api/admin/me", "admin"), ("/ADMIN/equipment", "admin"),
    ("//admin/x", "admin"), ("/Api/Admin/me", "admin"),
    ("/field", "field"), ("/api/health", "field"), ("/assets/a.js", "field"), ("/administrator", "field"), ("/", "field"),
])
def test_scope_of_path(path, scope):
    assert scope_of_path(path) == scope


def test_unavailable_lists_allow_only_the_server_pc():
    lists = AccessLists(unavailable=True)
    for scope in ("field", "admin"):
        assert not is_allowed(lists, parse_ip("192.168.3.5"), scope)
        assert not is_allowed(lists, None, scope)
        assert is_allowed(lists, parse_ip("127.0.0.1"), scope) and is_allowed(lists, parse_ip("::1"), scope)
