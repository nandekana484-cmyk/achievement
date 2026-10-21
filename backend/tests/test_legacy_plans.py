import sqlite3
from datetime import datetime, timedelta

import pytest

from app.core.clock import JST
from app.integration.legacy_plans import (
    LegacySourceError,
    find_monthly_dbs,
    parse_legacy_datetime,
    parse_takt_sec,
    read_active_plans,
    read_legacy_source,
    read_takt_master,
)
from legacy_fixture import (
    TAKT,
    add_monthly_db,
    deactivate,
    insert_plan,
    make_legacy_app,
    make_master_db,
    make_plan_db,
    set_mtime,
)

NOW = datetime(2026, 10, 21, 8, 0, tzinfo=JST)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "plan.db"
    make_plan_db(p)
    return p


def test_reads_only_active_latest_version(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", qty=300)
    insert_plan(db, kitting_no="0722-1-S-251014-01", qty=300, start="2026/10/22 09:00:00")  # 日程変更=新しい版
    result = read_active_plans(db, TAKT)
    assert len(result.plans) == 1
    p = result.plans[0]
    assert p.legacy_version == 2
    assert p.planned_start == datetime(2026, 10, 22, 9, 0, tzinfo=JST)
    assert p.run_no == 1 and p.planned_qty == 300 and p.line_code == "S"


def test_skips_deactivated(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    deactivate(db, "0722-1-S-251014-01")
    assert read_active_plans(db, TAKT).plans == []


def test_invalid_kitting_no_becomes_warning(db):
    insert_plan(db, kitting_no="BROKEN")
    insert_plan(db, kitting_no="0722-1-S-251014-02")
    r = read_active_plans(db, TAKT)
    assert [p.kitting_no for p in r.plans] == ["0722-1-S-251014-02"]
    assert len(r.warnings) == 1 and r.warnings[0].kitting_no == "BROKEN"
    assert r.warnings[0].lot_no == "L001"  # 読めなかった行でも lot_no は入る


def test_bad_datetime_warning_has_key(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", lot_no="L009", start="21/10/2026 09:00")
    r = read_active_plans(db, TAKT)
    assert r.plans == []
    assert r.warnings[0].key == ("0722-1-S-251014-01", "L009")


def test_side_mismatch_warns_and_uses_side(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", side="2")
    r = read_active_plans(db, TAKT)
    assert r.plans[0].run_no == 2
    assert "面" in r.warnings[0].message


def test_does_not_write(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    before = db.read_bytes()
    read_active_plans(db, TAKT)
    assert db.read_bytes() == before


def test_readonly_connection_refuses_writes(db):
    from app.integration.legacy_plans import open_readonly

    conn = open_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE kitting_plan_items SET is_active = 0")
    conn.close()


def test_parse_datetime():
    assert parse_legacy_datetime("2026/07/01 00:00:00") == datetime(2026, 7, 1, tzinfo=JST)
    assert parse_legacy_datetime("2026-07-01 13:05:09") == datetime(2026, 7, 1, 13, 5, 9, tzinfo=JST)
    assert parse_legacy_datetime("") is None
    with pytest.raises(ValueError):
        parse_legacy_datetime("07/01/2026")


def test_fixture_closes_connections(db):
    # Windows では、接続が残っているとファイルを消せない
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    deactivate(db, "0722-1-S-251014-01")
    read_active_plans(db, TAKT)
    db.unlink()


# --- ロットごとの最終書き込み時刻 ---

def test_lot_last_written_includes_inactive_rows(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", lot_no="L001", at="2026-10-01 09:00:00")
    insert_plan(db, kitting_no="0722-2-S-251014-02", lot_no="L001", side="2", at="2026-10-02 09:00:00")
    insert_plan(db, kitting_no="0800-1-S-251014-03", lot_no="L002", file_no="0800", at="2026-10-03 09:00:00")
    deactivate(db, "0800-1-S-251014-03", "L002", at="2026-10-05 17:30:00")  # 無効にした時刻も書き込み

    r = read_active_plans(db, TAKT)

    assert r.lot_last_written == {
        "L001": datetime(2026, 10, 2, 9, 0, tzinfo=JST),
        "L002": datetime(2026, 10, 5, 17, 30, tzinfo=JST),
    }
    assert [p.lot_no for p in r.plans] == ["L001", "L001"]  # L002 は有効な行が無い


# --- 正規化 ---

def test_file_no_and_line_are_normalized(db):
    # 既存アプリと同じ正規化: 数字だけのファイルNo.は4桁にゼロ埋め、英字は大文字、全角は半角
    insert_plan(db, kitting_no="722-1-s-251014-01", file_no="722", line="ｓ")
    insert_plan(db, kitting_no="T458-1-S-251014-02", file_no="t458", line=" s ")

    r = read_active_plans(db, TAKT)

    by_kno = {p.kitting_no: p for p in r.plans}
    assert (by_kno["722-1-s-251014-01"].file_no, by_kno["722-1-s-251014-01"].line_code) == ("0722", "S")
    assert (by_kno["T458-1-S-251014-02"].file_no, by_kno["T458-1-S-251014-02"].line_code) == ("T458", "S")
    # キッティングNo.のライン記号(s)とも、正規化した値どうしで比べるので食い違いの警告は出ない
    assert not [w for w in r.warnings if "食い違" in w.message]


def test_line_mismatch_is_compared_after_normalization(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01", line="t")
    r = read_active_plans(db, TAKT)
    assert r.plans[0].line_code == "T"
    assert any("実装ライン(T)とキッティングNo.のライン(S)" in w.message for w in r.warnings)


def test_empty_file_no_and_line_fall_back_to_kitting_no(db):
    insert_plan(db, kitting_no="722-1-s-251014-01", file_no="", line="")
    p = read_active_plans(db, TAKT).plans[0]
    assert (p.file_no, p.line_code) == ("0722", "S")


# --- 想定タクト ---

def test_takt_is_attached(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    insert_plan(db, kitting_no="0722-2-S-251014-02", side="2")
    r = read_active_plans(db, TAKT)
    assert [p.takt_sec for p in r.plans] == [30.0, 55.72]
    assert r.warnings == []


def test_takt_missing_in_master_warns(db):
    insert_plan(db, kitting_no="0999-1-S-251014-01", file_no="0999")
    r = read_active_plans(db, TAKT)
    assert r.plans[0].takt_sec is None
    [w] = r.warnings
    assert "想定タクトがマスタにありません" in w.message and "0999" in w.message
    assert w.key == ("0999-1-S-251014-01", "L001")


def test_takt_not_a_number_warns(db):
    insert_plan(db, kitting_no="0722-1-S-251014-01")
    r = read_active_plans(db, {("0722", "S", 1): "abc"})
    assert r.plans[0].takt_sec is None
    assert "想定タクトを数値として読めません" in r.warnings[0].message


def test_no_takt_warning_for_unreadable_row(db):
    insert_plan(db, kitting_no="0999-1-S-251014-01", file_no="0999", start="21/10/2026")
    r = read_active_plans(db, TAKT)
    assert len(r.warnings) == 1 and "日時" in r.warnings[0].message


def test_parse_takt_sec():
    assert parse_takt_sec("30") == 30.0
    assert parse_takt_sec(" 55.72 ") == 55.72
    for bad in (None, "", "abc", "nan", "inf"):
        with pytest.raises(ValueError):
            parse_takt_sec(bad)


def test_read_takt_master_normalizes_keys(tmp_path):
    p = tmp_path / "master.db"
    make_master_db(p, {("722", "ｓ", "1"): "30", ("T458", "s", "2"): "55.72", ("0800", "S", "x"): "10"})
    assert read_takt_master(p) == {("0722", "S", 1): "30", ("T458", "S", 2): "55.72"}


def test_read_takt_master_conflict_after_normalization_warns(tmp_path):
    p = tmp_path / "master.db"
    make_master_db(p, {("722", "S", "1"): "30", ("0722", "S", "1"): "31"})  # 正規化すると同じキー
    db = tmp_path / "plan.db"
    make_plan_db(db)
    insert_plan(db, kitting_no="0722-1-S-251014-01")

    r = read_active_plans(db, read_takt_master(p))

    assert r.plans[0].takt_sec is None
    assert "値が異なる行があります" in r.warnings[0].message


# --- 月次DBの探索と読み取り ---

def test_find_monthly_dbs_skips_default_and_old(tmp_path):
    app = make_legacy_app(tmp_path / "app")
    make_plan_db(app / "db" / "inventory.db")  # 既定DB(未選択)
    new = add_monthly_db(app, "2026-10")
    old = add_monthly_db(app, "2026-05")
    (app / "db" / "empty-folder").mkdir()
    set_mtime(new, NOW - timedelta(days=1))
    set_mtime(old, NOW - timedelta(days=121))

    found, skipped = find_monthly_dbs(app, 120, NOW)

    assert [name for name, _, _ in found] == ["2026-10"]
    assert [s.name for s in skipped] == ["2026-05"]


def test_read_legacy_source_reads_all_and_prefixes_warnings(tmp_path):
    app = make_legacy_app(tmp_path / "app")
    a = add_monthly_db(app, "2026-09")
    b = add_monthly_db(app, "2026-10")
    insert_plan(a, kitting_no="0722-1-S-251014-01")
    insert_plan(b, kitting_no="BROKEN", lot_no="L002")

    src = read_legacy_source(app, 120, NOW)

    assert [(d.name, len(d.result.plans)) for d in src.dbs] == [("2026-09", 1), ("2026-10", 0)]
    assert src.dbs[1].result.warnings[0].message.startswith("[2026-10] ")
    assert src.dbs[0].file_mtime.tzinfo is not None


def test_read_legacy_source_fails_if_one_db_is_unreadable(tmp_path):
    app = make_legacy_app(tmp_path / "app")
    add_monthly_db(app, "2026-09")
    broken = app / "db" / "2026-10" / "inventory.db"
    broken.parent.mkdir()
    broken.write_bytes(b"this is not a sqlite database" * 100)

    with pytest.raises(LegacySourceError, match="2026-10"):
        read_legacy_source(app, 120, NOW)


def test_read_legacy_source_fails_without_monthly_db(tmp_path):
    app = make_legacy_app(tmp_path / "app")
    make_plan_db(app / "db" / "inventory.db")  # 既定DBだけ
    with pytest.raises(LegacySourceError, match="読む月次DBがありません"):
        read_legacy_source(app, 120, NOW)
