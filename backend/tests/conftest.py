from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import clock
from app.core.clock import JST
from app.db.migrate import upgrade_to_head
from app.db.session import make_engine
from legacy_fixture import make_plan_db


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
def legacy_db(tmp_path):
    p = tmp_path / "legacy" / "monthly.db"
    p.parent.mkdir()
    make_plan_db(p)
    return p
