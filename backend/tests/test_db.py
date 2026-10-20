from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, MetaData, Table, inspect, select, text

from app.core.clock import JST
from app.db.migrate import MIGRATIONS_DIR, upgrade_to_head
from app.db.types import TZDateTime


def test_upgrade_creates_tables_and_is_repeatable(engine):
    upgrade_to_head(engine)  # 2回目(起動のたびに呼ばれる)
    names = set(inspect(engine).get_table_names())
    assert {"plans", "plan_sync_runs", "plan_sync_warnings", "alembic_version"} <= names
    with engine.connect() as c:
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"


def test_migrations_dir_does_not_depend_on_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert MIGRATIONS_DIR.is_absolute() and (MIGRATIONS_DIR / "env.py").exists()


@pytest.fixture
def tz_table(engine):
    t = Table("tz_test", MetaData(), Column("v", TZDateTime))
    t.create(engine)
    return t


def test_tzdatetime_converts_to_jst(engine, tz_table):
    utc = datetime(2026, 10, 21, 0, 30, tzinfo=timezone.utc)
    with engine.begin() as c:
        c.execute(tz_table.insert().values(v=utc))
    with engine.connect() as c:
        v = c.execute(select(tz_table.c.v)).scalar_one()
    assert v == datetime(2026, 10, 21, 9, 30, tzinfo=JST)
    assert v.utcoffset() == timedelta(hours=9)


def test_tzdatetime_rejects_naive(engine, tz_table):
    with pytest.raises(Exception, match="タイムゾーン"):
        with engine.begin() as c:
            c.execute(tz_table.insert().values(v=datetime(2026, 10, 21, 9, 0)))
