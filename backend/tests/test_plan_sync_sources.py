"""既存アプリのすべての月次DBを読む同期(開発指針 6.1)。既存アプリと同じフォルダ構成を tmp_path に作って確かめる。"""

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.models import Plan, PlanSyncRun, PlanSyncWarning
from app.services.plan_sync import run_plan_sync
from legacy_fixture import (
    add_monthly_db,
    copy_lot,
    deactivate,
    insert_plan,
    make_plan_db,
    set_mtime,
    soft_delete_lot,
)

K1 = "0722-1-S-251014-01"
K2 = "0722-2-S-251014-02"


@pytest.fixture
def sync(session_factory, legacy_app, fake_clock):
    def _sync():
        fake_clock.advance(minutes=1)
        with session_factory() as s:
            return run_plan_sync(s, legacy_app)

    return _sync


@pytest.fixture
def sep(legacy_app):
    """前月の月次DB「2026-09」。legacy_db は当月の「2026-10」。"""
    return add_monthly_db(legacy_app, "2026-09")


def _plans(session_factory) -> dict[tuple[str, str], Plan]:
    with session_factory() as s:
        return {(p.kitting_no, p.lot_no): p for p in s.scalars(select(Plan))}


def _snapshot(session_factory) -> list[tuple]:
    with session_factory() as s:
        return [
            tuple(getattr(p, c.key) for c in Plan.__table__.columns)
            for p in s.scalars(select(Plan).order_by(Plan.kitting_no, Plan.lot_no))
        ]


def _open_warnings(session_factory) -> list[PlanSyncWarning]:
    with session_factory() as s:
        return list(s.scalars(select(PlanSyncWarning).where(PlanSyncWarning.resolved_at.is_(None))))


def _legacy_dbs(session_factory, run_id) -> dict:
    with session_factory() as s:
        return json.loads(s.get(PlanSyncRun, run_id).legacy_dbs)


def test_single_db_records_source_and_db_list(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    insert_plan(legacy_db, kitting_no=K2, side="2")

    r = sync()

    assert (r.result, r.added, r.cancelled) == ("ok", 2, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.source_db == "2026-10" and p.takt_sec == 30.0
    assert _plans(session_factory)[(K2, "L001")].takt_sec == 55.72
    dbs = _legacy_dbs(session_factory, r.sync_run_id)
    assert [(d["name"], d["plans"], d["lots"], d["adopted_plans"]) for d in dbs["read"]] == [("2026-10", 2, 1, 2)]
    assert dbs["skipped"] == []


def test_carryover_to_new_db_moves_source_without_change(sync, session_factory, legacy_db, sep):
    insert_plan(sep, kitting_no=K1, at="2026-10-01 09:00:00")
    insert_plan(sep, kitting_no=K2, side="2", at="2026-10-01 09:00:00")
    sync()
    before = _plans(session_factory)[(K1, "L001")]
    assert before.source_db == "2026-09"

    copy_lot(sep, legacy_db, "L001", at="2026-10-15 08:00:00")  # 前月からの引き継ぎ(時刻はコピーした時刻)
    r = sync()

    assert (r.added, r.changed, r.unchanged, r.cancelled) == (0, 0, 2, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.source_db == "2026-10"
    assert p.updated_at == before.updated_at  # 内容は変わっていない


def test_edit_in_old_db_during_inventory_overlap_wins(sync, session_factory, legacy_db, sep):
    insert_plan(sep, kitting_no=K1, at="2026-10-01 09:00:00")
    copy_lot(sep, legacy_db, "L001", at="2026-10-15 08:00:00")
    sync()
    assert _plans(session_factory)[(K1, "L001")].source_db == "2026-10"

    # 棚卸の期間中に、既存アプリで古いDBに切り替えて計画を修正した
    insert_plan(sep, kitting_no=K1, qty=250, at="2026-10-20 13:00:00")
    r = sync()

    assert (r.changed, r.cancelled) == (1, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.source_db == "2026-09" and p.planned_qty == 250


def test_finished_lot_only_in_old_db_is_not_cancelled(sync, session_factory, legacy_db, sep):
    insert_plan(sep, kitting_no=K1, start="2026/09/28 09:00:00", end="2026/09/28 12:00:00", at="2026-09-27 09:00:00")
    insert_plan(legacy_db, kitting_no="0800-1-S-251014-03", lot_no="L002", file_no="0800", at="2026-10-15 09:00:00")

    sync()
    r = sync()

    assert r.cancelled == 0
    plans = _plans(session_factory)
    assert plans[(K1, "L001")].status == "active" and plans[(K1, "L001")].source_db == "2026-09"


def test_soft_delete_in_source_db_cancels(sync, session_factory, legacy_db, sep):
    insert_plan(sep, kitting_no=K1, at="2026-10-01 09:00:00")
    copy_lot(sep, legacy_db, "L001", at="2026-10-15 08:00:00")
    sync()

    soft_delete_lot(legacy_db, "L001", at="2026-10-20 15:00:00")  # 正とするDBで削除(ソフト)
    r = sync()

    # 古いDBには有効な行が残っているが、正とするDB(最後に書き込まれたDB)で消えたので取消
    assert r.cancelled == 1
    assert _plans(session_factory)[(K1, "L001")].status == "cancelled"


def test_restored_db_with_old_times_is_not_source(sync, session_factory, legacy_db, sep, fake_clock):
    insert_plan(legacy_db, kitting_no=K1, qty=300, at="2026-10-15 09:00:00")
    # バックアップから戻したDB: 中身の時刻は古いまま、ファイルの更新日時は新しい
    insert_plan(sep, kitting_no=K1, qty=999, at="2026-10-01 09:00:00")
    set_mtime(sep, fake_clock.current + timedelta(hours=1))

    sync()

    p = _plans(session_factory)[(K1, "L001")]
    assert p.source_db == "2026-10" and p.planned_qty == 300


def test_same_time_uses_file_mtime_and_warns_if_different(sync, session_factory, legacy_db, sep, fake_clock):
    insert_plan(legacy_db, kitting_no=K1, qty=300, at="2026-10-15 09:00:00")
    insert_plan(sep, kitting_no=K1, qty=250, at="2026-10-15 09:00:00")
    set_mtime(legacy_db, fake_clock.current - timedelta(hours=2))
    set_mtime(sep, fake_clock.current - timedelta(hours=1))  # こちらが新しい

    sync()

    p = _plans(session_factory)[(K1, "L001")]
    assert p.source_db == "2026-09" and p.planned_qty == 250
    [w] = _open_warnings(session_factory)
    assert w.lot_no == "L001" and "最終書き込み時刻が同じで内容が異なる" in w.message
    assert "「2026-09」を正とします" in w.message


def test_same_time_same_content_has_no_warning(sync, session_factory, legacy_db, sep, fake_clock):
    insert_plan(legacy_db, kitting_no=K1, at="2026-10-15 09:00:00")
    insert_plan(sep, kitting_no=K1, at="2026-10-15 09:00:00")
    set_mtime(legacy_db, fake_clock.current - timedelta(hours=1))
    set_mtime(sep, fake_clock.current - timedelta(hours=2))

    sync()

    assert _plans(session_factory)[(K1, "L001")].source_db == "2026-10"
    assert _open_warnings(session_factory) == []


def test_one_unreadable_db_is_error_and_changes_nothing(sync, session_factory, legacy_db, legacy_app):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    deactivate(legacy_db, K1)  # 本来なら取消になる変更
    before = _snapshot(session_factory)

    broken = legacy_app / "db" / "2026-11" / "inventory.db"
    broken.parent.mkdir()
    broken.write_bytes(b"this is not a sqlite database" * 100)
    r = sync()

    assert r.result == "error" and "2026-11" in r.error_message
    assert _snapshot(session_factory) == before


def test_lot_missing_from_all_dbs_is_kept_with_warning(sync, session_factory, legacy_db, sep, fake_clock):
    insert_plan(sep, kitting_no=K1, at="2026-10-01 09:00:00")
    insert_plan(legacy_db, kitting_no="0800-1-S-251014-03", lot_no="L002", file_no="0800", at="2026-10-15 09:00:00")
    sync()
    before = _snapshot(session_factory)

    set_mtime(sep, fake_clock.current - timedelta(days=200))  # 古すぎて読まなくなった → L001 はどこにも無い
    r = sync()

    assert (r.result, r.cancelled, r.changed) == ("ok", 0, 0)
    assert _snapshot(session_factory) == before  # 値も状態も変えない
    msgs = [(w.lot_no, w.message) for w in _open_warnings(session_factory)]
    assert ("L001", "ロットがどの月次DBにも見つかりません。このロットの計画は取消にせず、そのままにします") in msgs


def test_plan_ended_before_today_is_not_cancelled(sync, session_factory, legacy_db):
    past = "0722-1-S-251014-05"
    insert_plan(legacy_db, kitting_no=past, start="2026/10/20 09:00:00", end="2026/10/20 23:59:00")
    insert_plan(legacy_db, kitting_no=K1)  # 今日の計画
    sync()
    before_past = _plans(session_factory)[(past, "L001")]

    deactivate(legacy_db, past, at="2026-10-21 07:00:00")
    deactivate(legacy_db, K1, at="2026-10-21 07:00:00")
    r = sync()

    assert r.cancelled == 1
    plans = _plans(session_factory)
    assert plans[(K1, "L001")].status == "cancelled"
    assert plans[(past, "L001")].status == "active"  # 計画終了が今日の 0:00 より前
    assert plans[(past, "L001")].updated_at == before_past.updated_at


def test_default_db_and_old_db_are_not_read(sync, session_factory, legacy_db, legacy_app, fake_clock):
    default_db = legacy_app / "db" / "inventory.db"
    make_plan_db(default_db)
    insert_plan(default_db, kitting_no="0901-1-S-251014-01", lot_no="L901", file_no="0901")
    old = add_monthly_db(legacy_app, "2026-05")
    insert_plan(old, kitting_no="0902-1-S-251014-01", lot_no="L902", file_no="0902")
    set_mtime(old, fake_clock.current - timedelta(days=121))
    insert_plan(legacy_db, kitting_no=K1)

    r = sync()

    assert r.added == 1 and list(_plans(session_factory)) == [(K1, "L001")]
    dbs = _legacy_dbs(session_factory, r.sync_run_id)
    assert [d["name"] for d in dbs["read"]] == ["2026-10"]
    assert [d["name"] for d in dbs["skipped"]] == ["2026-05"]


def test_normalized_values_and_takt_in_sync(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no="722-1-s-251014-01", file_no="722", line="ｓ")
    insert_plan(legacy_db, kitting_no="0999-1-S-251014-02", file_no="999")  # マスタに無い

    r = sync()

    plans = _plans(session_factory)
    p = plans[("722-1-s-251014-01", "L001")]
    assert (p.file_no, p.line_code, p.takt_sec) == ("0722", "S", 30.0)
    assert plans[("0999-1-S-251014-02", "L001")].takt_sec is None
    [w] = _open_warnings(session_factory)
    assert w.kitting_no == "0999-1-S-251014-02"
    assert w.message == "[2026-10] 想定タクトがマスタにありません(ファイルNo. 0999、ライン S、面 1)"
    assert r.warnings == 1


def test_warnings_only_from_source_db(sync, session_factory, legacy_db, sep):
    # 古いDBに残った読めない行(正としないDBの行)の警告は出さない
    insert_plan(sep, kitting_no=K1, at="2026-10-01 09:00:00")
    insert_plan(sep, kitting_no=K2, side="2", start="壊れた日時", at="2026-10-01 09:00:00")
    insert_plan(legacy_db, kitting_no=K1, at="2026-10-15 09:00:00")
    insert_plan(legacy_db, kitting_no=K2, side="2", at="2026-10-15 09:00:00")

    r = sync()

    assert r.added == 2 and r.warnings == 0
