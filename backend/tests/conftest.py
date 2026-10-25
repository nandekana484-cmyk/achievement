from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import clock
from app.core.clock import JST
from app.db.migrate import upgrade_to_head
from app.db.session import make_engine
from legacy_fixture import add_monthly_db, make_legacy_app


@pytest.fixture(autouse=True)
def _reset_ip_throttle():
    """ログインの失敗の数(接続元ごと)はプロセスの中に残るので、テストごとに戻す。"""
    from app.services.login_throttle import ip_throttle

    ip_throttle.reset()
    yield
    ip_throttle.reset()


@pytest.fixture(autouse=True)
def _fast_scrypt(request, monkeypatch):
    """テストを速くするため、scrypt を弱くする。強さそのものを確かめるテストは @pytest.mark.real_scrypt を付ける。"""
    if request.node.get_closest_marker("real_scrypt"):
        return
    from app.domain import passwords
    from app.services import admin_auth

    monkeypatch.setattr(passwords, "_N", 2**10)
    monkeypatch.setattr(admin_auth, "DUMMY_HASH", passwords.hash_password("dummy-for-tests"))


@pytest.fixture(autouse=True)
def _reset_ip_access():
    """アクセス制限の一覧の覚え(短い間だけ覚える)と、拒否のログのまとめを、テストごとに戻す。"""
    from app.ip_access import deny_log
    from app.services.ip_allowlist import cache

    cache.reset()
    deny_log.reset()
    yield
    cache.reset()
    deny_log.reset()


class FakeClock:
    """clock.now() を差し替える。advance() で時刻を進められる。"""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> datetime:
        self.current += timedelta(**kwargs)
        return self.current


@pytest.fixture
def fake_clock(monkeypatch):
    fc = FakeClock(datetime(2026, 10, 21, 8, 0, tzinfo=JST))
    monkeypatch.setattr(clock, "now", fc)
    return fc


@pytest.fixture
def engine(tmp_path):
    e = make_engine(tmp_path / "app" / "genba.db")
    upgrade_to_head(e)
    yield e
    e.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def legacy_app(tmp_path):
    """既存アプリのフォルダ(master.db と、月次DB「2026-10」が1つ)。"""
    app_dir = make_legacy_app(tmp_path / "legacy-app")
    add_monthly_db(app_dir, "2026-10")
    return app_dir


@pytest.fixture
def legacy_db(legacy_app):
    """legacy_app の月次DB「2026-10」。"""
    return legacy_app / "db" / "2026-10" / "inventory.db"
