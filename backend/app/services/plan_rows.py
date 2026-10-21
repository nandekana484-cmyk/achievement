"""本アプリの計画の行(plans)と、既存DBから読んだ計画(LegacyPlan)の行き来。"""

from __future__ import annotations

from app.db.models import Plan
from app.domain.kitting_no import parse_kitting_no
from app.integration.legacy_plans import LegacyPlan


def to_legacy(row: Plan) -> LegacyPlan:
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


def apply_plan(row: Plan, plan: LegacyPlan, source_db: str) -> None:
    """既存DBの計画の値を、本アプリの計画の行に写す。"""
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
    apply_tracking(row, plan, source_db)


def apply_tracking(row: Plan, plan: LegacyPlan, source_db: str) -> None:
    """内容の変化として数えない値(行番号・版・削除フラグ・正とするDB)を写す。"""
    row.legacy_plan_item_id = plan.legacy_plan_item_id
    row.legacy_version = plan.legacy_version
    row.delete_flag = plan.delete_flag
    row.source_db = source_db
