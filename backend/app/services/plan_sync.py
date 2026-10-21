"""計画の同期(開発指針 6.1)。既存アプリのすべての月次DBの有効な計画を読み、本アプリの plans に反映する。

- 既存DBは integration/legacy_plans.py 経由で読み取り専用で読むだけ
- ロットごとに、最後に書き込まれた月次DBを正とする(services/plan_source.py)
- 差分は内容で判定し(services/plan_diff.py)、自動で反映する
- 計画は物理削除しない。既存側で消えた計画は status=cancelled にする
- 1回の同期は1トランザクション。失敗したら反映は取り消し、result=error を記録する
  (月次DBが1つでも読めなければ、どのDBが正か決められないので何も反映しない)
- 次の計画は、消えても取消にせず、値も状態も変えない
  - 形式エラーで読めなかった行の計画(既存DBに行はある)
  - どの月次DBにも見当たらなくなったロットの計画(警告を出す)
  - 計画終了が今日の 0:00 より前の計画(古い月次DBが読む対象から外れても、過去の計画を残すため)
- 取消が多すぎるときは何も反映しない(result=guarded)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import SyncConfig
from app.db.models import (
    PLAN_ACTIVE,
    PLAN_CANCELLED,
    SYNC_ERROR,
    SYNC_GUARDED,
    SYNC_OK,
    SYNC_SKIPPED,
    Plan,
    PlanSyncRun,
    PlanSyncWarning,
)
from app.domain.kitting_no import parse_kitting_no
from app.integration.legacy_plans import LegacyPlan, LegacySourceRead, ReadWarning, read_legacy_source
from app.services.plan_diff import PlanKey, diff_plans
from app.services.plan_source import SourceSelection, choose_sources

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanSyncResult:
    """同期1回分の結果。"""

    sync_run_id: int
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
    """同期を1回行い、plan_sync_runs に記録する。

    既存DBが無い・読めないなどの失敗は例外にせず、result=error として記録して返す。
    取消になる計画が多すぎるときは、何も反映せず result=guarded として記録して返す。
    """
    cfg = sync_config or SyncConfig()
    started_at = clock.now()
    legacy_dbs: str | None = None
    try:
        source = read_legacy_source(legacy_app_dir, cfg.legacy_db_max_age_days, started_at)
        sel = choose_sources(source.dbs)
        legacy_dbs = _legacy_dbs_json(source, sel)

        rows = {(p.kitting_no, p.lot_no): p for p in session.scalars(select(Plan))}
        current = {key: _to_legacy(p) for key, p in rows.items() if p.status == PLAN_ACTIVE}
        # TODO(実績テーブル作成後): 実績のある計画のキーを渡す
        keys_with_actuals: set[PlanKey] = set()
        diff = diff_plans(current, sel.plans, keys_with_actuals)
        incoming = {p.key: p for p in sel.plans}

        removed, warnings = _plans_to_cancel(
            diff.removed_without_actuals + diff.removed_with_actuals, rows, incoming, sel, clock.now(),
        )
        removed_set = set(removed)
        carryovers = [c for c in diff.carryovers if c.old_key in removed_set]

        guard = _cancel_guard_reason(len(removed), len(current), cfg)
        if guard is not None:
            session.rollback()
            logger.warning("計画の同期を反映しませんでした: %s", guard)
            return record_sync_run(session, started_at, SYNC_GUARDED, guard, legacy_dbs)

        now = clock.now()
        added = revived = 0
        for plan in diff.added:
            row = rows.get(plan.key)
            if row is None:
                row = Plan(kitting_no=plan.kitting_no, lot_no=plan.lot_no, first_seen_at=now)
                session.add(row)
                added += 1
            else:
                logger.info("取消になっていた計画が既存DBに戻りました: %s", plan.key)
                revived += 1
            _apply(row, plan, sel.plan_sources[plan.key])
            row.status = PLAN_ACTIVE
            row.cancelled_at = None
            row.updated_at = now

        for plan in diff.changed:
            row = rows[plan.key]
            _apply(row, plan, sel.plan_sources[plan.key])
            row.updated_at = now

        for key in diff.unchanged:
            # 内容は同じでも、既存側の行番号・版・正とするDBは変わることがあるので、追跡用に合わせておく
            _apply_tracking(rows[key], incoming[key], sel.plan_sources[key])

        for key in removed:
            row = rows[key]
            row.status = PLAN_CANCELLED
            row.cancelled_at = now
            row.updated_at = now

        if carryovers:
            # TODO(実績テーブル作成後): 引き継ぎ(候補が1つなら自動で移す、複数なら管理画面で選ぶ)
            logger.info("引き継ぎの候補: %d件(未対応)", len(carryovers))

        _update_warnings(session, warnings, now)
        run = PlanSyncRun(
            started_at=started_at,
            finished_at=clock.now(),
            result=SYNC_OK,
            added=added,
            revived=revived,
            changed=len(diff.changed),
            unchanged=len(diff.unchanged),
            cancelled=len(removed),
            legacy_dbs=legacy_dbs,
        )
        session.add(run)
        session.commit()
    except Exception as e:  # noqa: BLE001  失敗を記録してアプリは止めない
        session.rollback()
        logger.exception("計画の同期に失敗しました")
        return record_sync_run(session, started_at, SYNC_ERROR, f"{type(e).__name__}: {e}", legacy_dbs)

    result = PlanSyncResult(
        sync_run_id=run.id,
        result=SYNC_OK,
        added=run.added,
        revived=run.revived,
        changed=run.changed,
        unchanged=run.unchanged,
        cancelled=run.cancelled,
        warnings=len(warnings),
        carryover_candidates=len(carryovers),
    )
    logger.info("計画の同期: %s", result)
    return result


def _plans_to_cancel(
    missing: list[PlanKey], rows: dict[PlanKey, Plan], incoming: dict[PlanKey, LegacyPlan],
    sel: SourceSelection, now: datetime,
) -> tuple[list[PlanKey], list[ReadWarning]]:
    """正とするDBに無かった計画のうち、取消にするものを選ぶ。あわせて、この同期の警告をすべて返す。

    取消にするのは、ロットがどこかの月次DBにあり、かつ正とするDBにその計画が無いときだけ。
    """
    warnings = list(sel.warnings)
    # 形式エラーで読めなかった行の計画は、既存DBに行はあるので取消にしない(値も更新しない)
    unreadable = {w.key for w in sel.warnings if w.key is not None} - incoming.keys()
    today_start = datetime.combine(now.date(), time(), tzinfo=clock.JST)

    removed: list[PlanKey] = []
    vanished_lots: set[str] = set()
    for key in missing:
        row = rows[key]
        if key in unreadable:
            continue
        if row.planned_end is not None and row.planned_end < today_start:
            continue  # 終わった計画は、古い月次DBが読む対象から外れても残す
        if row.lot_no not in sel.lot_sources:
            vanished_lots.add(row.lot_no)
            continue
        removed.append(key)

    for lot in sorted(vanished_lots):
        warnings.append(ReadWarning(None, None, lot_no=lot, message=(
            "ロットがどの月次DBにも見つかりません。このロットの計画は取消にせず、そのままにします"
        )))
    return removed, warnings


def _legacy_dbs_json(source: LegacySourceRead, sel: SourceSelection) -> str:
    """その回に読んだ月次DBの一覧と、DBごとの計画の件数。"""
    adopted: dict[str, int] = {}
    for name in sel.plan_sources.values():
        adopted[name] = adopted.get(name, 0) + 1
    return json.dumps({
        "read": [
            {
                "name": db.name,
                "file_mtime": db.file_mtime.isoformat(timespec="seconds"),
                "plans": len(db.result.plans),  # そのDBの有効な計画(読めた行)
                "lots": len(db.result.lot_last_written),
                "adopted_plans": adopted.get(db.name, 0),  # 同期で使った計画(正とした計画)
            }
            for db in source.dbs
        ],
        "skipped": [
            {"name": s.name, "file_mtime": s.file_mtime.isoformat(timespec="seconds"), "reason": s.reason}
            for s in source.skipped
        ],
    }, ensure_ascii=False)


def _cancel_guard_reason(cancel_count: int, active_count: int, cfg: SyncConfig) -> str | None:
    """一括取消の安全装置。既存DBの設定の間違いなどで、計画が一斉に取消になるのを防ぐ。

    TODO(要確認): 一括取消の判定の閾値
    """
    if cancel_count >= cfg.cancel_guard_min and cancel_count >= active_count * cfg.cancel_guard_ratio:
        return (
            f"取消になる計画が多すぎるため、反映しませんでした"
            f"(取消 {cancel_count}件 / 有効な計画 {active_count}件。"
            f"閾値: {cfg.cancel_guard_min}件以上 かつ {cfg.cancel_guard_ratio:.0%}以上)。"
            f"既存DBの設定や切り替えを確認してください"
        )
    return None


def record_sync_run(
    session: Session, started_at: datetime, result: str, message: str, legacy_dbs: str | None = None,
) -> PlanSyncResult:
    """計画を反映しなかった同期(error / skipped / guarded)を記録する。"""
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


def _to_legacy(row: Plan) -> LegacyPlan:
    """本アプリの計画を、差分の判定ができるよう LegacyPlan に戻す。"""
    return LegacyPlan(
        kitting_no=row.kitting_no,
        lot_no=row.lot_no,
        file_no=row.file_no,
        line_code=row.line_code,
        product_name=row.product_name,
        run_no=row.run_no,
        planned_qty=row.planned_qty,
        cumulative_qty=row.cumulative_qty,
        order_qty=row.order_qty,
        planned_start=row.planned_start,
        planned_end=row.planned_end,
        deadline=row.deadline,
        delete_flag=row.delete_flag,
        status=row.legacy_status,
        legacy_plan_item_id=row.legacy_plan_item_id,
        legacy_version=row.legacy_version,
        takt_sec=row.takt_sec,
    )


def _apply(row: Plan, plan: LegacyPlan, source_db: str) -> None:
    kno = parse_kitting_no(plan.kitting_no)
    row.file_no = plan.file_no
    row.line_code = plan.line_code
    row.product_name = plan.product_name
    row.run_no = plan.run_no
    row.planned_qty = plan.planned_qty
    row.cumulative_qty = plan.cumulative_qty
    row.order_qty = plan.order_qty
    row.planned_start = plan.planned_start
    row.planned_end = plan.planned_end
    row.deadline = plan.deadline
    row.legacy_status = plan.status
    row.takt_sec = plan.takt_sec
    row.issue_date = kno.issue_date
    row.issue_seq = kno.issue_seq
    _apply_tracking(row, plan, source_db)


def _apply_tracking(row: Plan, plan: LegacyPlan, source_db: str) -> None:
    """内容の変化として数えない値。削除フラグは考慮しないが、保存はしておく。"""
    row.legacy_plan_item_id = plan.legacy_plan_item_id
    row.legacy_version = plan.legacy_version
    row.delete_flag = plan.delete_flag
    row.source_db = source_db


def _update_warnings(session: Session, warnings: list[ReadWarning], now: datetime) -> None:
    """警告を (kitting_no, lot_no, message) ごとに1件にまとめて記録する。

    出続けている警告は last_seen_at を更新し、出なくなった警告には resolved_at を入れる。
    再び出たら resolved_at を空に戻す。
    """
    existing: dict[tuple, PlanSyncWarning] = {}
    for row in session.scalars(select(PlanSyncWarning).order_by(PlanSyncWarning.id)):
        existing[(row.kitting_no, row.lot_no, row.message)] = row

    seen: set[tuple] = set()
    for w in warnings:
        key = (w.kitting_no, w.lot_no, w.message)
        if key in seen:
            continue
        seen.add(key)
        row = existing.get(key)
        if row is None:
            session.add(PlanSyncWarning(
                kitting_no=w.kitting_no, lot_no=w.lot_no, message=w.message,
                legacy_plan_item_id=w.legacy_plan_item_id, first_seen_at=now, last_seen_at=now,
            ))
        else:
            row.legacy_plan_item_id = w.legacy_plan_item_id
            row.last_seen_at = now
            row.resolved_at = None

    for key, row in existing.items():
        if key not in seen and row.resolved_at is None:
            row.resolved_at = now
