import sqlite3
from datetime import datetime

import pytest

from app.core.clock import JST
from app.integration.legacy_plans import parse_legacy_datetime, read_active_plans
from legacy_fixture import deactivate, insert_plan, make_plan_db


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "plan.db"
    make_plan_db(p)
    return p


def test_reads_only_active_latest_version(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", qty=300)
    insert_plan(db, kitting_no="0722-1-S-251014-01", qty=300, start="2026/10/22 09:00:00")  # 日程変更=新しい版
    result = read_active_plans(db)
    assert len(result.plans) == 1
    p = result.plans[0]
    assert p.legacy_version == 2
    assert p.planned_start == datetime(2026, 10, 22, 9, 0, tzinfo=JST)
    assert p.run_no == 1 and p.planned_qty == 300 and p.line_code == "S"


def test_skips_deactivated(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    deactivate(db, "0722-1-S-251014-01")
    assert read_active_plans(db).plans == []


def test_invalid_kitting_no_becomes_warning(db):
    insert_plan(db, kitting_no="BROKEN")
    insert_plan(db, kitting_no="0722-1-S-251014-02")
    r = read_active_plans(db)
    assert [p.kitting_no for p in r.plans] == ["0722-1-S-251014-02"]
    assert len(r.warnings) == 1 and r.warnings[0].kitting_no == "BROKEN"
    assert r.warnings[0].lot_no == "L001"  # 読めなかった行でも lot_no は入る


def test_bad_datetime_warning_has_key(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", lot_no="L009", start="21/10/2026 09:00")
    r = read_active_plans(db)
    assert r.plans == []
    assert r.warnings[0].key == ("0722-1-S-251014-01", "L009")


def test_side_mismatch_warns_and_uses_side(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", side="2")
    r = read_active_plans(db)
    assert r.plans[0].run_no == 2
    assert "面" in r.warnings[0].message


def test_does_not_write(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    before = db.read_bytes()
    read_active_plans(db)
    assert db.read_bytes() == before


def test_readonly_connection_refuses_writes(db):
    from app.integration.legacy_plans import open_readonly

    conn = open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE kitting_plan_items SET is_active = 0")
    conn.close()


def test_parse_datetime():
    assert parse_legacy_datetime("2026/07/01 00:00:00") == datetime(2026, 7, 1, tzinfo=JST)
    assert parse_legacy_datetime("") is None
    with pytest.raises(ValueError):
        parse_legacy_datetime("07/01/2026")


def test_fixture_closes_connections(db):
    # Windows では、接続が残っているとファイルを消せない
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    deactivate(db, "0722-1-S-251014-01")
    read_active_plans(db)
    db.unlink()
