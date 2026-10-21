"""既存アプリの作業者(master.db の workers)の読み込み。計画の同期のたびに行う。"""

import pytest
from sqlalchemy import select

from app.db.models import Operator, PlanSyncWarning
from app.services import masters
from app.services.plan_sync import NO_WORKERS_TABLE, run_plan_sync
from legacy_fixture import delete_worker, drop_workers_table, put_worker


@pytest.fixture
def master(legacy_app):
    return legacy_app / "db" / "master.db"


@pytest.fixture
def sync(session_factory, legacy_app, fake_clock):
    def _sync():
        fake_clock.advance(minutes=1)
        with session_factory() as s:
            r = run_plan_sync(s, legacy_app)
        assert r.result == "ok", r.error_message
        return r

    return _sync


def _operators(session_factory) -> dict[str, tuple]:
    with session_factory() as s:
        return {o.worker_id: (o.name, o.role, o.active, o.source) for o in s.scalars(select(Operator))}


def _warnings(session_factory) -> list[str]:
    with session_factory() as s:
        return [w.message for w in s.scalars(select(PlanSyncWarning).where(PlanSyncWarning.resolved_at.is_(None)))]


def test_workers_are_added_with_name_role_and_state(sync, session_factory, master):
    put_worker(master, "Y001", "山田", "operator")
    put_worker(master, "a01", "管理者", "admin")
    put_worker(master, "R9", "退職者", active=False)
    sync()
    assert _operators(session_factory) == {
        "Y001": ("山田", "operator", True, "legacy"),
        "a01": ("管理者", "admin", True, "legacy"),  # 表記は既存アプリのまま
        "R9": ("退職者", "operator", False, "legacy"),
    }


def test_name_role_and_state_follow_legacy(sync, session_factory, master):
    put_worker(master, "Y001", "山田")
    sync()
    put_worker(master, "Y001", "山田 太郎", "admin", active=False)
    sync()
    assert _operators(session_factory)["Y001"] == ("山田 太郎", "admin", False, "legacy")
    put_worker(master, "Y001", "山田 太郎", "admin", active=True)  # 有効に戻る
    sync()
    assert _operators(session_factory)["Y001"][2] is True


def test_worker_missing_from_legacy_is_deactivated_not_deleted(sync, session_factory, master):
    put_worker(master, "Y001", "山田")
    put_worker(master, "S002", "佐藤")
    sync()
    delete_worker(master, "S002")
    sync()
    ops = _operators(session_factory)
    assert ops["S002"] == ("佐藤", "operator", False, "legacy")  # 消さずに無効(過去の記録が参照しているため)
    assert ops["Y001"][2] is True


def test_ids_colliding_after_normalization_import_only_one(sync, session_factory, master):
    put_worker(master, "AB01", "一人目")
    put_worker(master, "ａｂ01", "二人目")  # 全角・小文字の違いを除くと AB01 と同じ
    sync()
    assert _operators(session_factory) == {"AB01": ("一人目", "operator", True, "legacy")}
    [w] = _warnings(session_factory)
    assert "「ａｂ01」は「AB01」と" in w and "取り込みません" in w


def test_changed_notation_keeps_the_same_operator(sync, session_factory, master):
    put_worker(master, "y001", "山田")
    sync()
    with session_factory() as s:
        before = s.scalars(select(Operator)).one().id
    delete_worker(master, "y001")
    put_worker(master, "Y001", "山田")  # 表記だけ変わった → 同じ作業者として扱う
    sync()
    with session_factory() as s:
        op = s.scalars(select(Operator)).one()
    assert (op.id, op.worker_id, op.active) == (before, "Y001", True)


def test_local_operator_with_same_id_is_not_overwritten(sync, session_factory, master):
    with session_factory() as s:
        masters.add_operator(s, "開発用", worker_id="Y001")
    put_worker(master, "y001", "山田")
    sync()
    assert _operators(session_factory) == {"Y001": ("開発用", "operator", True, "local")}
    assert any("開発用に足した作業者と重なる" in w for w in _warnings(session_factory))


def test_local_operators_are_not_deactivated(sync, session_factory, master):
    with session_factory() as s:
        masters.add_operator(s, "開発用", worker_id="D1")
    sync()
    assert _operators(session_factory)["D1"][2] is True


def test_missing_workers_table_warns_and_changes_nothing(sync, session_factory, master):
    put_worker(master, "Y001", "山田")
    sync()
    drop_workers_table(master)
    sync()
    assert _operators(session_factory)["Y001"][2] is True  # 無効にしない
    assert NO_WORKERS_TABLE in _warnings(session_factory)
