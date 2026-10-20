from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.clock import JST
from app.db.models import Plan, PlanSyncRun, PlanSyncWarning
from app.services.plan_sync import run_plan_sync
from legacy_fixture import deactivate, insert_plan

K1 = "0722-1-S-251014-01"
K2 = "0722-2-S-251014-02"


@pytest.fixture
def sync(session_factory, legacy_db, fake_clock):
    def _sync():
        fake_clock.advance(minutes=1)
        with session_factory() as s:
            return run_plan_sync(s, legacy_db)

    return _sync


def _plans(session_factory) -> dict[tuple[str, str], Plan]:
    with session_factory() as s:
        return {(p.kitting_no, p.lot_no): p for p in s.scalars(select(Plan))}


def _snapshot(session_factory) -> list[tuple]:
    with session_factory() as s:
        return [
            tuple(getattr(p, c.key) for c in Plan.__table__.columns)
            for p in s.scalars(select(Plan).order_by(Plan.kitting_no, Plan.lot_no))
        ]


def test_added(sync, session_factory, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no=K1, qty=300)
    insert_plan(legacy_db, kitting_no=K2, side="2", qty=300)

    r = sync()

    assert (r.result, r.added, r.changed, r.unchanged, r.cancelled) == ("ok", 2, 0, 0, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.status == "active"
    assert p.planned_qty == 300 and p.run_no == 1 and p.line_code == "S" and p.file_no == "0722"
    assert p.issue_date == date(2025, 10, 14) and p.issue_seq == 1
    assert p.planned_start == datetime(2026, 10, 21, 9, 0, tzinfo=JST)
    assert p.first_seen_at == p.updated_at == fake_clock.current
    assert p.cancelled_at is None and p.legacy_version == 1


def test_schedule_change_updates_values(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    first = _plans(session_factory)[(K1, "L001")]

    insert_plan(legacy_db, kitting_no=K1, start="2026/10/22 09:00:00", end="2026/10/22 12:00:00")
    r = sync()

    assert (r.added, r.changed, r.unchanged) == (0, 1, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.planned_start == datetime(2026, 10, 22, 9, 0, tzinfo=JST)
    assert p.legacy_version == 2
    assert p.updated_at > first.updated_at
    assert p.first_seen_at == first.first_seen_at


def test_reimport_same_content_is_unchanged(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    first = _plans(session_factory)[(K1, "L001")]

    new_item_id = insert_plan(legacy_db, kitting_no=K1)  # 版だけ上がる
    r = sync()

    assert (r.added, r.changed, r.unchanged, r.cancelled) == (0, 0, 1, 0)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.updated_at == first.updated_at
    # 追跡用の行番号と版は、既存側の最新に合わせる
    assert p.legacy_version == 2 and p.legacy_plan_item_id == new_item_id


def test_deactivated_becomes_cancelled(sync, session_factory, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no=K1)
    sync()

    deactivate(legacy_db, K1)
    r = sync()

    assert r.cancelled == 1
    p = _plans(session_factory)[(K1, "L001")]  # 行は消えない
    assert p.status == "cancelled"
    assert p.cancelled_at == fake_clock.current


def test_delete_flag_becomes_cancelled(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()

    insert_plan(legacy_db, kitting_no=K1, delete_flag=1)
    r = sync()

    assert r.cancelled == 1
    assert _plans(session_factory)[(K1, "L001")].status == "cancelled"


def test_cancelled_plan_comes_back(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    deactivate(legacy_db, K1)
    sync()

    insert_plan(legacy_db, kitting_no=K1, qty=250)
    r = sync()

    assert (r.added, r.cancelled) == (1, 0)
    plans = _plans(session_factory)
    assert len(plans) == 1
    p = plans[(K1, "L001")]
    assert p.status == "active" and p.cancelled_at is None and p.planned_qty == 250


def test_missing_legacy_db_records_error(session_factory, tmp_path, fake_clock):
    with session_factory() as s:
        r = run_plan_sync(s, tmp_path / "nothing.db")

    assert r.result == "error"
    assert "既存DBが見つかりません" in r.error_message
    with session_factory() as s:
        run = s.get(PlanSyncRun, r.sync_run_id)
        assert run.result == "error" and run.error_message == r.error_message
        assert s.scalars(select(Plan)).all() == []


def test_error_keeps_existing_plans(sync, session_factory, legacy_db, tmp_path):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    before = _snapshot(session_factory)

    with session_factory() as s:  # 既存DBが読めなくなった(ファイルが無い)
        r = run_plan_sync(s, tmp_path / "moved.db")

    assert r.result == "error"
    assert _snapshot(session_factory) == before  # 読めないときに取消にしない


def test_sync_twice_is_idempotent(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    insert_plan(legacy_db, kitting_no=K2, side="2")
    sync()
    deactivate(legacy_db, K2)
    sync()
    before = _snapshot(session_factory)

    r = sync()

    assert (r.added, r.changed, r.unchanged, r.cancelled) == (0, 0, 1, 0)
    assert _snapshot(session_factory) == before


def test_read_warnings_are_recorded(sync, session_factory, legacy_db):
    bad_id = insert_plan(legacy_db, kitting_no="BROKEN")
    insert_plan(legacy_db, kitting_no=K1)

    r = sync()

    assert r.added == 1 and r.warnings == 1
    with session_factory() as s:
        w = s.scalars(select(PlanSyncWarning)).one()
        assert w.sync_run_id == r.sync_run_id
        assert w.legacy_plan_item_id == bad_id and w.kitting_no == "BROKEN"


def test_legacy_db_files_are_not_changed(sync, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    folder = legacy_db.parent
    before = {f.name: f.read_bytes() for f in folder.iterdir()}

    sync()
    sync()

    assert {f.name: f.read_bytes() for f in folder.iterdir()} == before


def test_times_are_read_back_with_jst(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    r = sync()

    nine = timedelta(hours=9)
    with session_factory() as s:  # 新しいセッションで、DBから読み直す
        p = s.scalars(select(Plan)).one()
        for v in (p.planned_start, p.planned_end, p.deadline, p.first_seen_at, p.updated_at):
            assert v.utcoffset() == nine
            assert v.isoformat().endswith("+09:00")
        run = s.get(PlanSyncRun, r.sync_run_id)
        assert run.started_at.utcoffset() == nine and run.finished_at.utcoffset() == nine
