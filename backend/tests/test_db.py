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
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003"


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


def test_upgrade_from_0001_keeps_sync_runs(tmp_path):
    from alembic import command

    from app.db.migrate import alembic_config
    from app.db.session import make_engine

    e = make_engine(tmp_path / "old.db")
    cfg = alembic_config()
    with e.begin() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0001")
        c.execute(text(
            "INSERT INTO plan_sync_runs (started_at, finished_at, result, added, changed, unchanged, cancelled)"
            " VALUES ('2026-10-21 09:00:00.000000', '2026-10-21 09:00:01.000000', 'ok', 1, 0, 0, 0)"
        ))
    upgrade_to_head(e)
    with e.connect() as c:
        assert c.execute(text("SELECT added, revived FROM plan_sync_runs")).one() == (1, 0)
    e.dispose()


def test_upgrade_from_0002_keeps_plans(tmp_path):
    from alembic import command

    from app.db.migrate import alembic_config
    from app.db.session import make_engine

    e = make_engine(tmp_path / "old.db")
    cfg = alembic_config()
    with e.begin() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0002")
        c.execute(text(
            "INSERT INTO plans (kitting_no, lot_no, file_no, line_code, product_name, run_no, planned_qty,"
            " delete_flag, legacy_plan_item_id, legacy_version, issue_date, issue_seq, status, first_seen_at, updated_at)"
            " VALUES ('0722-1-S-251014-01', 'L001', '0722', 'S', '基板A', 1, 300, 0, 1, 1, '2025-10-14', 1, 'active',"
            " '2026-10-21 09:00:00.000000', '2026-10-21 09:00:00.000000')"
        ))
    upgrade_to_head(e)
    with e.connect() as c:
        assert c.execute(text("SELECT planned_qty, takt_sec, source_db FROM plans")).one() == (300, None, None)
        assert c.execute(text("SELECT legacy_dbs FROM plan_sync_runs")).all() == []
    e.dispose()
