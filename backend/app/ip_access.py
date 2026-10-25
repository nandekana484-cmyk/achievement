"""登録したIPアドレスだけにアクセスを許す(画面、API、静的ファイルのすべて)。詳細: docs/design/security.md(アクセス制限)

判定に使うのは、TCP 接続の相手のアドレス(scope["client"])だけ。X-Forwarded-For などのヘッダーは見ない。
許可しないときは 403(API は JSON、それ以外は日本語の短い画面)。拒否はログに残す(同じIPは1分に1回)。
"""

from __future__ import annotations

import html
import json
import logging
import threading
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.domain.networks import is_allowed, parse_ip, scope_of_path
from app.services.ip_allowlist import cache

logger = logging.getLogger(__name__)

DENIED_MESSAGE = "あなたのIPは許可されていません。管理者に連絡してください"
LOG_INTERVAL_SECONDS = 60.0

_PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>アクセスできません</title>
<style>body{{font-family:sans-serif;margin:3rem 1.5rem;line-height:1.6}}h1{{font-size:1.4rem}}small{{color:#666}}</style></head>
<body><h1>{message}</h1><p><small>接続元: {ip}</small></p></body></html>
"""


class DenyLog:
    """拒否のログを、同じIPは1分に1回にまとめる(連続した要求でログを埋めないため)。"""

    def __init__(self, interval: float = LOG_INTERVAL_SECONDS) -> None:
        self._interval = interval
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}
        self._skipped: dict[str, int] = {}

    def record(self, ip: str, path: str) -> None:
        now = time.monotonic()
        with self._lock:
            last = self._last.get(ip)
            if last is not None and now - last < self._interval:
                self._skipped[ip] = self._skipped.get(ip, 0) + 1
                return
            skipped = self._skipped.pop(ip, 0)
            if len(self._last) > 1000:
                self._last = {k: t for k, t in self._last.items() if now - t < self._interval}
            self._last[ip] = now
        extra = f"(直前の1分間に、ほかに{skipped}回)" if skipped else ""
        logger.warning("アクセス制限で拒否しました: 接続元 %s、パス %s%s", ip, path, extra)

    def reset(self) -> None:
        with self._lock:
            self._last.clear()
            self._skipped.clear()


deny_log = DenyLog()


class IpAccessMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        lists = cache.get()
        if not lists.field and not lists.admin:  # 制限していない(今までどおり)
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        host = client[0] if client else None
        path = scope["path"]
        if is_allowed(lists, parse_ip(host), scope_of_path(path)):
            await self.app(scope, receive, send)
            return
        deny_log.record(host or "(不明)", path)
        await self._deny(scope, send, host or "(不明)")

    async def _deny(self, scope: Scope, send: Send, host: str) -> None:
        if scope_is_api(scope["path"]):
            body, ctype = json.dumps({"detail": DENIED_MESSAGE}, ensure_ascii=False).encode(), b"application/json"
        else:
            body, ctype = _PAGE.format(message=DENIED_MESSAGE, ip=html.escape(host)).encode(), b"text/html; charset=utf-8"
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", ctype), (b"content-length", str(len(body)).encode()), (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})


def scope_is_api(path: str) -> bool:
    p = "/" + path.lower().lstrip("/")
    return p == "/api" or p.startswith("/api/")
