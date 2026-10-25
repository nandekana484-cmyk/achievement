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
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0013"


def test_models_match_migrations(engine):
    # モデル(app/db/models.py)を変えたのにマイグレーションを足し忘れていないか
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.session import Base

    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diff == []


def test_reasons_are_seeded(engine):
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT name, category, requires_equipment, requires_text, usable_as_line_event, usable_as_restart,"
            " counts_in_utilization FROM reasons ORDER BY sort_order"
        )).all()
    assert [r[0] for r in rows] == [
        "部品探し", "欠品", "マシントラブル", "立上立会", "応援・その他", "その他トラブル", "人員交代", "トラブル停止", "計画切替",
    ]
    by_name = {r[0]: r[1:] for r in rows}
    assert by_name["マシントラブル"] == ("loss", 1, 0, 1, 1, 0)
    assert by_name["その他トラブル"] == ("loss", 0, 1, 1, 1, 0)
    assert by_name["立上立会"] == ("non_loss", 0, 0, 1, 0, 0)
    assert by_name["人員交代"] == ("non_loss", 0, 0, 0, 1, 0)
    assert all(r[6] == 0 for r in rows)  # 稼働率に含めるかは要確認。今はすべて含めない


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
        # 0004: それまでに取り込んだ計画のラインが登録される
        assert c.execute(text("SELECT line_code, name FROM lines")).all() == [("S", "Sライン")]
    e.dispose()


def test_reason_names_vi_are_seeded(engine):
    with engine.connect() as c:
        rows = dict(c.execute(text("SELECT name, name_vi FROM reasons")).all())
    assert rows["部品探し"] == "Tìm linh kiện" and rows["マシントラブル"] == "Sự cố máy"
    assert rows["応援・その他"] == "Hỗ trợ / Khác" and rows["計画切替"] == "Chuyển kế hoạch"
    assert all(rows.values())  # 初期の9件すべてに入る


def test_0009_does_not_overwrite_names_set_by_people(tmp_path):
    from alembic import command

    from app.db.migrate import alembic_config
    from app.db.session import make_engine

    e = make_engine(tmp_path / "old.db")
    cfg = alembic_config()
    with e.begin() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0008")
        c.execute(text("UPDATE reasons SET name_vi = 'Tìm phụ tùng' WHERE name = '部品探し'"))
        c.execute(text("UPDATE reasons SET name_vi = '  ' WHERE name = '欠品'"))  # 空白だけは空とみなす
    upgrade_to_head(e)
    with e.connect() as c:
        rows = dict(c.execute(text("SELECT name, name_vi FROM reasons")).all())
    assert rows["部品探し"] == "Tìm phụ tùng" and rows["欠品"] == "Thiếu linh kiện"

    with e.begin() as c:  # 戻すと、0009 で入れた値のものだけ空になる
        cfg.attributes["connection"] = c
        command.downgrade(cfg, "0008")
    with e.connect() as c:
        rows = dict(c.execute(text("SELECT name, name_vi FROM reasons")).all())
    assert rows["部品探し"] == "Tìm phụ tùng" and rows["欠品"] is None
    e.dispose()
