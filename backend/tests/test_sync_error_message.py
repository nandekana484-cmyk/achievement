"""計画の同期の失敗の文に、パスや例外の文を出さない(S-12)。詳細はログに残す。詳細: docs/design/security.md"""

from __future__ import annotations

import logging

from app.db.models import PlanSyncRun
from app.services import plan_sync
from app.services.plan_sync import run_plan_sync


def test_missing_legacy_app_message_has_no_path(session_factory, tmp_path, fake_clock, caplog):
    secret_dir = tmp_path / "SecretFolderName"
    with caplog.at_level(logging.WARNING), session_factory() as s:
        r = run_plan_sync(s, secret_dir)
    assert r.result == "error" and "master.db" in r.error_message
    assert "SecretFolderName" not in r.error_message and str(tmp_path) not in r.error_message
    with session_factory() as s:
        run = s.get(PlanSyncRun, r.sync_run_id)
        assert "SecretFolderName" not in run.error_message
    assert "SecretFolderName" in caplog.text  # 詳細はログに残る


def test_unexpected_error_is_generic_in_the_screen_and_detailed_in_the_log(session_factory, tmp_path, fake_clock, monkeypatch, caplog):
    def boom(*_a, **_k):
        raise RuntimeError(f"cannot open {tmp_path}/SecretFolderName/x.db")

    monkeypatch.setattr(plan_sync, "read_legacy_source", boom)
    with caplog.at_level(logging.ERROR), session_factory() as s:
        r = run_plan_sync(s, tmp_path)
    assert r.result == "error"
    assert "SecretFolderName" not in r.error_message and "RuntimeError" not in r.error_message
    assert "ログ" in r.error_message
    assert "SecretFolderName" in caplog.text


def test_sync_status_api_shows_no_path(session_factory, tmp_path, fake_clock):
    from app.api.plans import SyncRunOut

    with session_factory() as s:
        r = run_plan_sync(s, tmp_path / "SecretFolderName")
        run = s.get(PlanSyncRun, r.sync_run_id)
        assert "SecretFolderName" not in SyncRunOut.model_validate(run).model_dump_json()
