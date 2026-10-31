"""計画の同期の手順(開発指針 6.1)。既存アプリのすべての月次DBを読み、本アプリの plans に反映する。

取消の判定は plan_cancel.py、警告の記録は plan_sync_warnings.py。詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import SyncConfig
from app.db.models import (
    SYNC_ERROR,
    SYNC_GUARDED,
    SYNC_OK,
    SYNC_SKIPPED,
    PlanSyncRun,
)
from app.db.session import is_busy_error, write_transaction
from app.integration.legacy.workers import LegacyWorker
from app.integration.legacy_plans import (
    LegacySourceError,
    LegacySourceRead,
    ReadWarning,
    read_legacy_source,
    read_master_workers,
)
from app.services.masters import register_lines
from app.services.plan_changes import plan_changes, write_changes
from app.services.plan_source import SourceSelection, choose_sources
from app.services.plan_sync_warnings import update_warnings
from app.services.teitori_sync import TeitoriRead, read_teitori_for_sync, sync_teitori
from app.services.worker_sync import sync_operators, sync_operators_alone

logger = logging.getLogger(__name__)

NO_WORKERS_TABLE = "master.db に作業者の表(workers)がありません。作業者は読み込みません"


@dataclass(frozen=True)
class PlanSyncResult:
    """同期1回分の結果。"""

    sync_run_id: int | None  # 書き込みが重なって記録できなかったときだけ None
    result: str  # ok / error / skipped / guarded
    added: int = 0
    revived: int = 0  # 取消から復活した計画
    changed: int = 0
    unchanged: int = 0
    cancelled: int = 0
    warnings: int = 0
    carryover_candidates: int = 0
    error_message: str | None = None


def run_plan_sync(session: Session, legacy_app_dir: Path, sync_config: SyncConfig | None = None) -> PlanSyncResult:
    """同期を1回行い、plan_sync_runs に記録する。失敗は例外にせず result=error として返す。

    既存DBの読み取りと正とするDBの決定はロックの外で行い、反映する部分だけを write_transaction の中で行う。
    """
    cfg = sync_config or SyncConfig()
    started_at = clock.now()
    legacy_dbs: str | None = None
    workers, workers_note = _read_workers(legacy_app_dir)
    teitori = read_teitori_for_sync(legacy_app_dir)
    try:
        source = read_legacy_source(legacy_app_dir, cfg.legacy_db_max_age_days, started_at)
        sel = choose_sources(source.dbs)
        legacy_dbs = _legacy_dbs_json(source, sel)
        with write_transaction(session):
            return _apply_selection(session, sel, cfg, started_at, legacy_dbs, workers, workers_note, teitori)
    except Exception as e:  # noqa: BLE001  失敗を記録してアプリは止めない
        session.rollback()
        logger.exception("計画の同期に失敗しました")
        sync_operators_alone(session, workers)  # 計画を読めなくても、作業者は読み込む
        return _record_error(session, started_at, public_error_message(e), legacy_dbs)


def public_error_message(e: Exception) -> str:
    """同期の失敗の理由のうち、画面(認証なしの /api/sync/status)に出してよい文。パスや例外の文は出さず、詳細はログに残す。"""
    if isinstance(e, LegacySourceError):
        return e.public
    return "計画の同期で想定外のエラーが起きました。詳細はログ(genba.log)を見てください"


def _read_workers(legacy_app_dir: Path) -> tuple[list[LegacyWorker] | None, str]:
    """作業者を計画とは切り離して読む。読めないときは None と、警告に出す理由。"""
    try:
        return read_master_workers(legacy_app_dir), NO_WORKERS_TABLE
    except LegacySourceError as e:
        logger.warning("作業者を読めません: %s", e)
        return None, e.public


def _record_error(session: Session, started_at: datetime, message: str, legacy_dbs: str | None) -> PlanSyncResult:
    try:
        return record_sync_run(session, started_at, SYNC_ERROR, message, legacy_dbs)
    except OperationalError as busy:
        if not is_busy_error(busy):
            raise
        # 失敗の記録もできなかった。次の回にやり直す
        session.rollback()
        logger.warning("計画の同期の失敗を記録できませんでした(書き込みが重なったため): %s", busy)
        return PlanSyncResult(sync_run_id=None, result=SYNC_ERROR, error_message=message)


def _apply_selection(
    session: Session, sel: SourceSelection, cfg: SyncConfig, started_at: datetime, legacy_dbs: str,
    workers: list[LegacyWorker] | None = None, workers_note: str = NO_WORKERS_TABLE,
    teitori: TeitoriRead | None = None,
) -> PlanSyncResult:
    """正とするDBの計画を本アプリの plans に反映し、コミットまで行う(write_transaction の中で呼ぶ)。"""
    changes = plan_changes(session, sel, cfg)
    if changes.guard is not None:
        session.rollback()
        logger.warning("計画の同期を反映しませんでした: %s", changes.guard)
        return record_sync_run(session, started_at, SYNC_GUARDED, changes.guard, legacy_dbs)

    now = clock.now()
    added, revived = write_changes(session, changes, sel, now)
    if changes.carryovers:
        # 引き継ぎは自動で行わない。管理画面の「引き継ぎの確認」で管理者が確定する(詳細: docs/design/legacy-integration.md)
        logger.info("引き継ぎの候補: %d件(管理画面の「引き継ぎの確認」で確定する)", len(changes.carryovers))
    new_lines = register_lines(session, {p.line_code for p in sel.plans})
    if new_lines:
        logger.info("新しいラインを登録しました: %s", ", ".join(new_lines))
    if workers is None:
        changes.warnings.append(ReadWarning(None, None, workers_note))
    else:
        changes.warnings.extend(sync_operators(session, workers))
    if teitori is not None:  # 丁取りが読めなくても同期は失敗にしない(前回の値を使い、警告だけ出す)
        changes.warnings.extend(sync_teitori(session, teitori, now))
    update_warnings(session, changes.warnings, now)

    run = PlanSyncRun(
        started_at=started_at, finished_at=clock.now(), result=SYNC_OK,
        added=added, revived=revived, changed=len(changes.diff.changed), unchanged=len(changes.diff.unchanged),
        cancelled=changes.cancelled_count, legacy_dbs=legacy_dbs,
    )
    session.add(run)
    session.commit()
    result = PlanSyncResult(
        sync_run_id=run.id, result=SYNC_OK, added=added, revived=revived,
        changed=run.changed, unchanged=run.unchanged, cancelled=run.cancelled,
        warnings=len(changes.warnings), carryover_candidates=len(changes.carryovers),
    )
    logger.info("計画の同期: %s", result)
    return result


def _legacy_dbs_json(source: LegacySourceRead, sel: SourceSelection) -> str:
    """その回に読んだ月次DBの一覧と、DBごとの計画の件数(plan_sync_runs.legacy_dbs)。"""
    adopted: dict[str, int] = {}
    for name in sel.plan_sources.values():
        adopted[name] = adopted.get(name, 0) + 1
    return json.dumps({
        "read": [
            {
                "name": db.name,
                "file_mtime": db.file_mtime.isoformat(timespec="seconds"),
                "plans": len(db.result.plans),
                "lots": len(db.result.lot_last_written),
                "adopted_plans": adopted.get(db.name, 0),
            }
            for db in source.dbs
        ],
        "skipped": [
            {"name": s.name, "file_mtime": s.file_mtime.isoformat(timespec="seconds"), "reason": s.reason}
            for s in source.skipped
        ],
    }, ensure_ascii=False)


def record_sync_run(
    session: Session, started_at: datetime, result: str, message: str, legacy_dbs: str | None = None,
) -> PlanSyncResult:
    """計画を反映しなかった同期(error / skipped / guarded)を記録する。"""
    with write_transaction(session):
        run = PlanSyncRun(
            started_at=started_at, finished_at=clock.now(), result=result,
            added=0, revived=0, changed=0, unchanged=0, cancelled=0, error_message=message,
            legacy_dbs=legacy_dbs,
        )
        session.add(run)
        session.commit()
    return PlanSyncResult(sync_run_id=run.id, result=result, error_message=message)


def record_skipped(session: Session, message: str) -> PlanSyncResult:
    return record_sync_run(session, clock.now(), SYNC_SKIPPED, message)
