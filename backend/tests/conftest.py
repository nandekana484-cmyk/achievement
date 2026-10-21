from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import clock
from app.core.clock import JST
from app.db.migrate import upgrade_to_head
from app.db.session import make_engine
from legacy_fixture import add_monthly_db, make_legacy_app


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
