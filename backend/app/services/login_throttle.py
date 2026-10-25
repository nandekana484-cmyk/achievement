"""管理画面のログインの失敗を、接続元のIPアドレスごとに数える(S-07)。作業者IDごとの制限(admin_auth)に加えて掛ける。

別のIDを次々に試す攻撃と、存在しないIDで失敗の行を増やす攻撃を止める。1プロセスで動かす前提なので、数えるのはメモリの中
(再起動で消える)。詳細: docs/design/security.md
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from app.core import clock
from app.core.config import AdminConfig
from app.services.errors import TooManyAttempts

_MAX_ENTRIES = 1000  # これを超えたら、期限の切れたものを捨てる(メモリを増やし続けない)


class IpThrottle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, datetime] = {}

    def check(self, ip: str) -> None:
        """この接続元が締め出されていたら TooManyAttempts。"""
        now = clock.now()
        with self._lock:
            until = self._locked_until.get(ip)
            if until is not None and until > now:
                minutes = max(1, int((until - now).total_seconds() // 60) + 1)
                raise TooManyAttempts(f"この端末からの失敗が続いたため、しばらくログインできません(あと約{minutes}分)")

    def failed(self, ip: str, cfg: AdminConfig) -> None:
        now = clock.now()
        with self._lock:
            if len(self._failures) > _MAX_ENTRIES:
                self._prune(now)
            self._failures[ip] = self._failures.get(ip, 0) + 1
            if self._failures[ip] >= cfg.ip_lockout_failures:
                self._failures.pop(ip)
                self._locked_until[ip] = now + timedelta(minutes=cfg.ip_lockout_minutes)

    def succeeded(self, ip: str) -> None:
        with self._lock:
            self._failures.pop(ip, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()

    def _prune(self, now: datetime) -> None:
        self._locked_until = {ip: t for ip, t in self._locked_until.items() if t > now}
        self._failures.clear()


ip_throttle = IpThrottle()
