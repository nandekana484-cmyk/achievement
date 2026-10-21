from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.clock import JST
from app.core.config import SyncConfig
from app.db.models import Plan, PlanSyncRun, PlanSyncWarning
from app.services.plan_sync import run_plan_sync
from legacy_fixture import deactivate, insert_plan

K1 = "0722-1-S-251014-01"
K2 = "0722-2-S-251014-02"


@pytest.fixture
def sync(session_factory, legacy_app, fake_clock):
    def _sync():
        fake_clock.advance(minutes=1)
        with session_factory() as s:
            return run_plan_sync(s, legacy_app)

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


def test_delete_flag_is_ignored(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()

    insert_plan(legacy_db, kitting_no=K1, delete_flag=1)
    r = sync()

    # 削除フラグは考慮しない(取消にも、内容の変更にもしない)。保存だけする
    assert (r.cancelled, r.changed, r.unchanged) == (0, 0, 1)
    p = _plans(session_factory)[(K1, "L001")]
    assert p.status == "active" and p.delete_flag is True


def test_cancelled_plan_comes_back(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    deactivate(legacy_db, K1)
    sync()

    insert_plan(legacy_db, kitting_no=K1, qty=250)
    r = sync()

    assert (r.added, r.revived, r.cancelled) == (0, 1, 0)
    with session_factory() as s:
        assert (s.get(PlanSyncRun, r.sync_run_id).added, s.get(PlanSyncRun, r.sync_run_id).revived) == (0, 1)
    plans = _plans(session_factory)
    assert len(plans) == 1
    p = plans[(K1, "L001")]
    assert p.status == "active" and p.cancelled_at is None and p.planned_qty == 250


def test_missing_legacy_app_records_error(session_factory, tmp_path, fake_clock):
    with session_factory() as s:
        r = run_plan_sync(s, tmp_path / "nothing")

    assert r.result == "error"
    assert "master.db を読めません" in r.error_message
    with session_factory() as s:
        run = s.get(PlanSyncRun, r.sync_run_id)
        assert run.result == "error" and run.error_message == r.error_message
        assert s.scalars(select(Plan)).all() == []


def test_error_keeps_existing_plans(sync, session_factory, legacy_db, tmp_path):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    before = _snapshot(session_factory)

    with session_factory() as s:  # 既存DBが読めなくなった(フォルダが無い)
        r = run_plan_sync(s, tmp_path / "moved")

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
        assert w.legacy_plan_item_id == bad_id and w.kitting_no == "BROKEN" and w.lot_no == "L001"
        assert w.resolved_at is None


def test_legacy_db_files_are_not_changed(sync, legacy_app, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)

    def files():
        return {
            f.relative_to(legacy_app): (f.read_bytes(), f.stat().st_mtime_ns)
            for f in legacy_app.rglob("*") if f.is_file()
        }

    before = files()

    sync()
    sync()

    assert files() == before  # 既存アプリのフォルダのファイルは、増えも変わりもしない


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


def _warnings(session_factory) -> list[PlanSyncWarning]:
    with session_factory() as s:
        return list(s.scalars(select(PlanSyncWarning).order_by(PlanSyncWarning.id)))


def test_unreadable_row_is_not_cancelled(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    before = _snapshot(session_factory)

    insert_plan(legacy_db, kitting_no=K1, start="21/10/2026 09:00")  # 既存側で日時の書式が壊れた
    r = sync()

    assert r.result == "ok" and (r.changed, r.cancelled) == (0, 0) and r.warnings == 1
    assert _snapshot(session_factory) == before  # active のまま、値も更新しない


def test_same_warning_is_kept_as_one(sync, session_factory, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no="BROKEN")
    sync()
    first_seen = fake_clock.current
    sync()
    sync()

    [w] = _warnings(session_factory)
    assert w.first_seen_at == first_seen
    assert w.last_seen_at == fake_clock.current
    assert w.resolved_at is None


def test_warning_resolves_and_recurs(sync, session_factory, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no="BROKEN")
    sync()

    deactivate(legacy_db, "BROKEN")  # 直った
    sync()
    [w] = _warnings(session_factory)
    assert w.resolved_at == fake_clock.current

    insert_plan(legacy_db, kitting_no="BROKEN")  # 再発
    sync()
    [w] = _warnings(session_factory)
    assert w.resolved_at is None and w.last_seen_at == fake_clock.current


def test_warnings_unchanged_when_sync_fails(sync, session_factory, legacy_db, tmp_path):
    insert_plan(legacy_db, kitting_no="BROKEN")
    sync()
    with session_factory() as s:
        run_plan_sync(s, tmp_path / "moved")
    [w] = _warnings(session_factory)
    assert w.resolved_at is None


def _many(legacy_db, n):
    keys = [f"{i:04d}-1-S-251014-{i:02d}" for i in range(1, n + 1)]
    for k in keys:
        insert_plan(legacy_db, kitting_no=k, file_no=k[:4])
    return keys


def test_mass_cancel_is_guarded(sync, session_factory, legacy_db):
    keys = _many(legacy_db, 12)
    sync()
    before = _snapshot(session_factory)

    for k in keys[:10]:  # 10件(83%)が一斉に消えた
        deactivate(legacy_db, k)
    insert_plan(legacy_db, kitting_no="0999-1-S-251020-01", file_no="0999")  # 同時に増えた計画も反映しない
    r = sync()

    assert r.result == "guarded"
    assert "取消 10件 / 計画終了が今日以降の有効な計画 12件" in r.error_message
    assert _snapshot(session_factory) == before
    with session_factory() as s:
        assert s.get(PlanSyncRun, r.sync_run_id).result == "guarded"


def test_cancel_below_min_is_applied(sync, session_factory, legacy_db):
    keys = _many(legacy_db, 9)
    sync()
    for k in keys:  # 全部消えても 9件 < 10件 なので反映する
        deactivate(legacy_db, k)
    r = sync()
    assert r.result == "ok" and r.cancelled == 9


def test_cancel_below_ratio_is_applied(sync, session_factory, legacy_db):
    keys = _many(legacy_db, 40)
    sync()
    for k in keys[:10]:  # 10件だが 10 / 40 = 25% < 30%
        deactivate(legacy_db, k)
    r = sync()
    assert r.result == "ok" and r.cancelled == 10


def _past(legacy_db, n, end="2026/10/20 12:00:00"):
    """計画終了が今日(2026-10-21)の 0:00 より前の計画。"""
    keys = [f"{i:04d}-1-S-251001-{i:02d}" for i in range(101, 101 + n)]
    for k in keys:
        insert_plan(legacy_db, kitting_no=k, file_no=k[:4], start="2026/10/20 09:00:00", end=end)
    return keys


def test_guard_ignores_past_plans_in_denominator(sync, session_factory, legacy_db):
    _past(legacy_db, 40)
    keys = _many(legacy_db, 12)
    sync()
    before = _snapshot(session_factory)

    for k in keys[:10]:  # 未来の計画が一斉に消えた(全体の 52件中では 19% だが、今日以降の 12件中 83%)
        deactivate(legacy_db, k)
    r = sync()

    assert r.result == "guarded"
    assert "取消 10件 / 計画終了が今日以降の有効な計画 12件" in r.error_message
    assert _snapshot(session_factory) == before


def test_guard_denominator_counts_plans_without_end(sync, session_factory, legacy_db):
    for i in range(30):  # 計画終了が空の計画は、終わっていないものとして分母に入る
        insert_plan(legacy_db, kitting_no=f"{i + 200:04d}-1-S-251001-{i:02d}", file_no=f"{i + 200:04d}", start="", end="")
    keys = _many(legacy_db, 10)
    sync()

    for k in keys:  # 10件 / 40件 = 25% < 30%
        deactivate(legacy_db, k)
    r = sync()

    assert r.result == "ok" and r.cancelled == 10


def test_guard_uses_config(session_factory, legacy_app, legacy_db, fake_clock):
    keys = _many(legacy_db, 3)
    with session_factory() as s:
        run_plan_sync(s, legacy_app)
    for k in keys[:2]:
        deactivate(legacy_db, k)
    with session_factory() as s:
        r = run_plan_sync(s, legacy_app, SyncConfig(cancel_guard_min=2, cancel_guard_ratio=0.5))
    assert r.result == "guarded"
