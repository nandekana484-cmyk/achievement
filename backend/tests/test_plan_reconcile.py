"""計画を読む条件を既存アプリにそろえる、出し直しで残る古い計画の扱い(AD-16)。詳細: docs/design/legacy-integration.md"""

import sqlite3
from contextlib import closing

import pytest
from sqlalchemy import select

from app.core.clock import JST
from app.core.config import SyncConfig
from app.db.models import Operator, Plan, PlanSyncWarning, RunEvent
from app.integration.legacy.plans import read_active_plans
from app.services.plan_source import NO_STALE_VIEW
from app.services.plan_sync import run_plan_sync
from legacy_fixture import TAKT, drop_stale_view, insert_plan, set_stale

K1 = "0722-1-S-251014-01"
K2 = "0722-1-S-251014-02"
NEW = "0722-1-S-251014-09"  # 出し直しで振り直されたキッティングNo.
OLD_DAY = dict(start="2026/10/18 09:00:00", end="2026/10/19 12:00:00")  # 計画終了が今日(10/21)の 0:00 より前


@pytest.fixture
def sync(session_factory, legacy_app, fake_clock):
    def _sync(cfg: SyncConfig | None = None):
        fake_clock.advance(minutes=1)
        with session_factory() as s:
            return run_plan_sync(s, legacy_app, cfg)

    return _sync


def _plans(session_factory) -> dict[tuple[str, str], Plan]:
    with session_factory() as s:
        return {(p.kitting_no, p.lot_no): p for p in s.scalars(select(Plan))}


def _warnings(session_factory) -> list[str]:
    with session_factory() as s:
        return [w.message for w in s.scalars(select(PlanSyncWarning).where(PlanSyncWarning.resolved_at.is_(None)))]


def add_actual(session_factory, kno: str) -> None:
    """実績(工程の記録)を1件入れる。"""
    with session_factory() as s:
        op = Operator(name="山田", worker_id="Y001", worker_key="y001", role="operator", source="local", active=True, sort_order=1)
        s.add(op)
        s.flush()
        s.add(RunEvent(kitting_no=kno, step_type="setup", seq=1, start_at=_t(9), end_at=_t(10), started_by=op.id, ended_by=op.id,
                       start_request_id=f"s-{kno}", end_request_id=f"e-{kno}", created_at=_t(10)))
        s.commit()


def _t(hour):
    from datetime import datetime

    return datetime(2026, 10, 21, hour, 0, tzinfo=JST)


def raw(path, sql, *args):
    with closing(sqlite3.connect(path)) as c, c:
        c.execute(sql, args)


# --- 計画を読む条件 ---

def test_delete_flag_one_row_is_not_read(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1, delete_flag=1)
    r = sync()
    assert r.added == 0 and _plans(session_factory) == {}


def test_null_is_active_row_is_read(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    raw(legacy_db, "UPDATE kitting_plan_items SET is_active = NULL")  # 既存アプリは NULL を有効として扱う
    assert sync().added == 1


def test_delete_flag_one_marks_existing_plan_cancelled_not_deleted(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    raw(legacy_db, "UPDATE kitting_plan_items SET delete_flag = 1")
    r = sync()
    p = _plans(session_factory)[(K1, "L001")]  # 行は消さない
    assert (r.cancelled, p.status, p.cancel_reason) == (1, "cancelled", "vanished")


def test_null_lot_and_empty_lot_are_the_same_key_as_the_view(legacy_db):
    insert_plan(legacy_db, kitting_no=K1, lot_no="X")
    insert_plan(legacy_db, kitting_no=K2, lot_no="Y")
    raw(legacy_db, "UPDATE kitting_plan_items SET lot_no = NULL WHERE kitting_list_no = ?", K1)
    raw(legacy_db, "UPDATE kitting_plan_items SET lot_no = '  ' WHERE kitting_list_no = ?", K2)  # 空白だけも ''
    set_stale(legacy_db, K1, "", "stale")
    set_stale(legacy_db, K2, "  ", "date_unparsable")  # ビューは保存された値のまま返す。読むときに前後の空白を除く
    result = read_active_plans(legacy_db, TAKT)
    assert {p.key for p in result.plans} == {(K1, ""), (K2, "")}
    assert result.stale is not None and {k: v.reason for k, v in result.stale.items()} == {(K1, ""): "stale", (K2, ""): "date_unparsable"}


def test_same_key_twice_keeps_newer_row_and_warns(sync, session_factory, legacy_db):
    raw(legacy_db, "DROP INDEX ux_active")  # 索引の無い古い月次DB
    insert_plan(legacy_db, kitting_no=K1, qty=100, at="2026-10-20 10:00:00")
    raw(legacy_db, "UPDATE kitting_plan_items SET is_active = 1")
    insert_plan(legacy_db, kitting_no=K1, qty=200, at="2026-10-20 12:00:00", lot_no="L001")
    raw(legacy_db, "UPDATE kitting_plan_items SET is_active = 1")
    r = sync()
    assert r.result == "ok" and r.added == 1  # 同期は止めない
    assert _plans(session_factory)[(K1, "L001")].planned_qty == 200  # updated_at が新しい方
    assert any("有効な行が2行以上あります" in w and "更新日時が新しい行" in w for w in _warnings(session_factory))


# --- 古い計画 ---

@pytest.mark.parametrize(("reason", "cancelled"), [
    ("stale", True), ("in_latest_batch", False), ("outside_period", False),
    ("date_unparsable", False), ("no_period", False), ("no_latest_batch", False),
])
def test_judge_reason_decides_the_handling(sync, session_factory, legacy_db, reason, cancelled):
    insert_plan(legacy_db, kitting_no=K1)
    set_stale(legacy_db, K1, "L001", reason)
    sync()
    plans = _plans(session_factory)
    if cancelled:
        assert (K1, "L001") not in plans  # 一度も有効にならなかった古い計画は、取り込まない
    else:
        assert plans[(K1, "L001")].status == "active" and plans[(K1, "L001")].is_stale is False
    undecided = [w for w in _warnings(session_factory) if "判定できない計画" in w]
    assert len(undecided) == (1 if reason in ("date_unparsable", "no_period", "no_latest_batch") else 0)
    assert all("1件" in w for w in undecided)


def test_stale_plan_without_actuals_is_cancelled_and_comes_back(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    set_stale(legacy_db, K1, "L001", "stale", replacement=NEW)
    r = sync()
    p = _plans(session_factory)[(K1, "L001")]
    assert (r.cancelled, p.status, p.cancel_reason, p.is_stale, p.replacement_kitting_no) == (1, "cancelled", "reissued", True, NEW)

    set_stale(legacy_db, K1, "L001", "in_latest_batch")  # 判定が古くないに戻った
    r = sync()
    p = _plans(session_factory)[(K1, "L001")]
    assert (r.revived, p.status, p.cancel_reason, p.is_stale) == (1, "active", None, False)


def test_stale_plan_ended_in_the_past_is_still_cancelled(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1, **OLD_DAY)
    sync()
    set_stale(legacy_db, K1, "L001", "stale")
    sync()
    assert _plans(session_factory)[(K1, "L001")].cancel_reason == "reissued"  # 実績が無いので、守る必要がない


def test_stale_plan_with_actuals_is_kept_with_a_warning(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    sync()
    add_actual(session_factory, K1)
    set_stale(legacy_db, K1, "L001", "stale", replacement=NEW)
    r = sync()
    p = _plans(session_factory)[(K1, "L001")]
    assert (r.cancelled, p.status, p.is_stale, p.replacement_kitting_no) == (0, "active", True, NEW)
    assert any("実績があるため取り消しません" in w for w in _warnings(session_factory))


def test_without_view_nothing_is_newly_cancelled_and_old_reissue_cancel_stays(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    insert_plan(legacy_db, kitting_no=K2)
    sync()
    set_stale(legacy_db, K1, "L001", "stale")
    sync()
    assert _plans(session_factory)[(K1, "L001")].cancel_reason == "reissued"

    set_stale(legacy_db, K2, "L001", "stale")  # 判定はあるが、ビューごと読めなくなる
    drop_stale_view(legacy_db)
    r = sync()
    plans = _plans(session_factory)
    assert r.result == "ok"  # 同期全体は失敗にしない
    assert plans[(K1, "L001")].status == "cancelled"  # 前の「出し直し」の取消を元に戻さない
    assert plans[(K2, "L001")].status == "active"  # 新しく取り消さない
    assert any(w == NO_STALE_VIEW.format(name="2026-10") for w in _warnings(session_factory))


def test_plan_still_cancels_without_view(sync, session_factory, legacy_db):
    insert_plan(legacy_db, kitting_no=K1)
    drop_stale_view(legacy_db)
    sync()
    raw(legacy_db, "UPDATE kitting_plan_items SET is_active = 0")
    r = sync()  # 計画そのものの取消・復活は、ビューが無くても今までどおり
    assert r.cancelled == 1 and _plans(session_factory)[(K1, "L001")].cancel_reason == "vanished"


def test_many_reissue_cancels_trip_the_guard(sync, session_factory, legacy_db):
    knos = [f"0722-1-S-251014-{i:02d}" for i in range(10, 20)]
    for k in knos:
        insert_plan(legacy_db, kitting_no=k, lot_no=f"L{k[-2:]}")
    sync()
    for k in knos:
        set_stale(legacy_db, k, f"L{k[-2:]}", "stale")
    r = sync()
    assert r.result == "guarded"  # 出し直しの取消も、10件以上かつ30%以上で止まる
    assert all(p.status == "active" for p in _plans(session_factory).values())
