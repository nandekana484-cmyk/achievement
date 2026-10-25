"""IPアドレスと範囲の扱いと、アクセスを許すかの判定(アクセス制限)。DBには触れない。詳細: docs/design/security.md

- IPv4 射影(::ffff:192.168.3.5)は IPv4 として扱う。IPv6 のゾーン(fe80::1%eth0)は外す
- 判定に使うのは、TCP 接続の相手のアドレスだけ(X-Forwarded-For などのヘッダーは使わない)
"""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network

IpAddress = IPv4Address | IPv6Address
Network = IPv4Network | IPv6Network

SCOPE_FIELD = "field"  # 現場の画面と API、静的ファイル
SCOPE_ADMIN = "admin"  # 管理画面(/admin、/api/admin)
SCOPES = (SCOPE_FIELD, SCOPE_ADMIN)
SCOPE_LABELS = {SCOPE_FIELD: "現場用", SCOPE_ADMIN: "管理画面用"}

BAD_FORMAT = "IPアドレスまたは範囲の書き方が正しくありません(例 192.168.3.5、192.168.3.0/24、fd00::/64)"
ALL_ADDRESSES = "すべてのアドレスを含む範囲(/0)は登録できません。制限をなくすには、一覧を空にしてください"


def parse_ip(text: str | None) -> IpAddress | None:
    """接続元の文字を IP アドレスにする。読めなければ None。IPv4 射影は IPv4 にする。"""
    if not text:
        return None
    try:
        ip = ip_address(text.strip().split("%", 1)[0])
    except ValueError:
        return None
    return ip.ipv4_mapped if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None else ip


def parse_network(text: str) -> Network:
    """登録する書き方(1台、または CIDR)を範囲にする。書き方が誤りなら ValueError(日本語の理由)。"""
    raw = (text or "").strip()
    try:
        if "/" not in raw:
            ip = parse_ip(raw)
            if ip is None:
                raise ValueError
            return ip_network(ip)  # 1台(IPv4 は /32、IPv6 は /128)
        net = ip_network(raw, strict=False)
    except ValueError:
        raise ValueError(BAD_FORMAT) from None
    if isinstance(net, IPv6Network) and net.network_address.ipv4_mapped is not None and net.prefixlen >= 96:
        net = ip_network(f"{net.network_address.ipv4_mapped}/{net.prefixlen - 96}", strict=False)  # ::ffff:a.b.c.d/120 → a.b.c.d/24
    if net.prefixlen == 0:
        raise ValueError(ALL_ADDRESSES)
    return net


def is_loopback(ip: IpAddress | None) -> bool:
    """サーバーのPC自身(127.0.0.0/8 と ::1)。常に許可する。"""
    return ip is not None and ip.is_loopback


@dataclass(frozen=True)
class AccessLists:
    """有効な範囲の一覧(現場用と管理画面用)。"""

    field: tuple[Network, ...] = ()
    admin: tuple[Network, ...] = ()

    @property
    def field_restricted(self) -> bool:
        return bool(self.field)

    @property
    def admin_restricted(self) -> bool:
        return bool(self.admin)


def _contains(networks: tuple[Network, ...], ip: IpAddress | None) -> bool:
    return ip is not None and any(ip.version == n.version and ip in n for n in networks)


def is_allowed(lists: AccessLists, ip: IpAddress | None, scope: str) -> bool:
    """この接続元に、この区分(現場/管理画面)を許すか。

    - サーバーのPC自身は常に許す
    - 現場用が空なら現場は制限しない。あれば、現場用か管理画面用に入っている接続元だけ(管理者は現場の画面も使えるように)
    - 管理画面は、管理画面用が空なら現場用と同じ。あれば、管理画面用に入っている接続元だけ
    """
    if is_loopback(ip):
        return True
    field_ok = not lists.field or _contains(lists.field, ip) or _contains(lists.admin, ip)
    if scope == SCOPE_ADMIN and lists.admin:
        return _contains(lists.admin, ip)
    return field_ok


def scope_of_path(path: str) -> str:
    """URL のパスがどちらの区分か(/admin と /api/admin の下は管理画面。大文字小文字は区別しない)。"""
    p = "/" + path.lower().lstrip("/")
    return SCOPE_ADMIN if p in ("/admin", "/api/admin") or p.startswith(("/admin/", "/api/admin/")) else SCOPE_FIELD
