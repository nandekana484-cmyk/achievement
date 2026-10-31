"""丁取り(master.db のビュー v_board_teitori)の取り込み。詳細: docs/design/metrics.md"""

import logging

import pytest
from sqlalchemy import select

from app.db.models import BoardTeitori, PlanSyncWarning
from app.integration.legacy.teitori import read_teitori
from app.services import teitori_sync
from app.services.plan_sync import run_plan_sync
from legacy_fixture import drop_teitori_view, insert_plan, make_master_db, put_teitori
K1 = "0722-1-S-251014-01"


@pytest.fixture(autouse=True)
def _reset_log_state():
    teitori_sync._last_message = None


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


def _rows(session_factory) -> dict[tuple[str, str], tuple]:
    with session_factory() as s:
        return {(r.setup_file_no, r.mounting_line): (r.teitori, r.status) for r in s.scalars(select(BoardTeitori))}


def _warnings(session_factory) -> list[str]:
    with session_factory() as s:
        return [w.message for w in s.scalars(select(PlanSyncWarning).where(PlanSyncWarning.resolved_at.is_(None)))]


def test_view_rows_are_copied_and_overwritten(sync, session_factory, master):
    sync()
    assert _rows(session_factory) == {("0722", "S"): (2, "ok"), ("0722", "T"): (4, "ok")}
    put_teitori(master, "0722", "S", None, "no_k_row")
    put_teitori(master, "0900", "S", 3, "ok")
    sync()
    assert _rows(session_factory) == {("0722", "S"): (None, "no_k_row"), ("0722", "T"): (4, "ok"), ("0900", "S"): (3, "ok")}
    assert not [w for w in _warnings(session_factory) if "v_board_teitori" in w]


def test_keys_are_normalized_like_the_legacy_app(master):
    put_teitori(master, "722", "s ", 2)  # 正規化していない値が来ても、既存アプリと同じ規則で直す
    put_teitori(master, "Ｔ４５８", "ｓ", 3)
    got = {(t.setup_file_no, t.mounting_line): t.teitori for t in read_teitori(master)}
    assert got[("0722", "S")] == 2 and got[("T458", "S")] == 3


def test_ok_without_valid_teitori_becomes_invalid(master):
    put_teitori(master, "0900", "S", 0, "ok")  # status が ok でも、1以上の整数でなければ使わない
    put_teitori(master, "0901", "S", 5, "multi_k")  # ok 以外では丁取り数を使わない
    got = {t.setup_file_no: (t.teitori, t.status) for t in read_teitori(master)}
    assert got["0900"] == (None, "teitori_invalid") and got["0901"] == (None, "multi_k")


def test_missing_view_does_not_fail_the_sync_and_keeps_previous_values(sync, session_factory, master, caplog):
    insert_plan(master.parent / "2026-10" / "inventory.db", kitting_no=K1)
    sync()
    before = _rows(session_factory)
    drop_teitori_view(master)
    with caplog.at_level(logging.WARNING):
        r = sync()
        sync()
    assert r.result == "ok" and r.added == 0
    assert _rows(session_factory) == before  # 前回の値をそのまま使う
    assert teitori_sync.NO_TEITORI_VIEW in _warnings(session_factory)  # 計画の同期の警告に出る
    assert [m for m in caplog.messages if "v_board_teitori" in m].__len__() == 1  # ログは1回だけ


def test_sync_without_view_from_the_start_succeeds(session_factory, legacy_app, fake_clock):
    (legacy_app / "db" / "master.db").unlink()
    make_master_db(legacy_app / "db" / "master.db", teitori=None)  # 既存アプリが 4.1.0 より前
    insert_plan(legacy_app / "db" / "2026-10" / "inventory.db", kitting_no=K1)
    with session_factory() as s:
        r = run_plan_sync(s, legacy_app)
    assert (r.result, r.added) == ("ok", 1)
    assert _rows(session_factory) == {}
    assert teitori_sync.NO_TEITORI_VIEW in _warnings(session_factory)


def test_warning_resolves_when_the_view_comes_back(sync, session_factory, legacy_app, master):
    drop_teitori_view(master)
    sync()
    assert teitori_sync.NO_TEITORI_VIEW in _warnings(session_factory)
    master.unlink()
    make_master_db(master, teitori={("0722", "S"): (2, "ok")})  # 作り直すのは、4.1.0 のアプリを入れたあとの状態
    sync()
    assert teitori_sync.NO_TEITORI_VIEW not in _warnings(session_factory)


def test_teitori_change_is_not_a_plan_change(sync, session_factory, master):
    insert_plan(master.parent / "2026-10" / "inventory.db", kitting_no=K1)
    sync()
    put_teitori(master, "0722", "S", 8)
    r = sync()
    assert (r.changed, r.cancelled, r.added) == (0, 0, 0)  # 計画の内容比較に入れない


def test_unreadable_master_keeps_teitori_but_fails_only_plans(sync, session_factory, master, monkeypatch):
    sync()
    before = _rows(session_factory)

    def boom(_):
        raise teitori_sync.LegacySourceError("detail", "master.db の丁取りを読めません。詳細はログを見てください")

    monkeypatch.setattr(teitori_sync, "read_master_teitori", boom)
    r = sync()
    assert r.result == "ok"
    assert _rows(session_factory) == before
    assert any("丁取りを読めません" in w for w in _warnings(session_factory))
