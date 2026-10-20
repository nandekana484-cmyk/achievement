import asyncio

from app.core.config import SyncConfig
from app.db.models import PlanSyncRun
from app.services import plan_sync_scheduler
from app.services.plan_sync_scheduler import PlanSyncScheduler, run_plan_sync_exclusive
from legacy_fixture import insert_plan


def test_exclusive_runs_sync(session_factory, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    r = run_plan_sync_exclusive(session_factory, legacy_db)
    assert r.result == "ok" and r.added == 1


def test_skipped_while_another_sync_is_running(session_factory, legacy_db, fake_clock):
    assert plan_sync_scheduler._lock.acquire(blocking=False)
    try:
        r = run_plan_sync_exclusive(session_factory, legacy_db)
    finally:
        plan_sync_scheduler._lock.release()

    assert r.result == "skipped"
    with session_factory() as s:
        assert s.get(PlanSyncRun, r.sync_run_id).result == "skipped"


def test_loop_continues_after_exception(monkeypatch, session_factory, legacy_db):
    calls = []

    def flaky(_factory, _path, _config):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("想定外のエラー")

    monkeypatch.setattr(plan_sync_scheduler, "run_plan_sync_exclusive", flaky)

    async def main():
        s = PlanSyncScheduler(session_factory, legacy_db, SyncConfig(plan_interval_sec=0.01))
        s.start()
        for _ in range(500):
            if len(calls) >= 3:
                break
            await asyncio.sleep(0.01)
        await s.stop()

    asyncio.run(main())
    assert len(calls) >= 3
