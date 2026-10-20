"""計画(plans)と計画の同期の記録(plan_sync_runs, plan_sync_warnings)

Revision ID: 0001
Revises:
Create Date: 2026-10-20

日時の列は sa.DateTime で作る(アプリ側の TZDateTime が日本時間に直して保存し、読み出すと +09:00 を付ける)。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("file_no", sa.String(), nullable=False),
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("run_no", sa.Integer(), nullable=False),
        sa.Column("planned_qty", sa.Integer(), nullable=False),
        sa.Column("cumulative_qty", sa.Integer(), nullable=True),
        sa.Column("order_qty", sa.Integer(), nullable=True),
        sa.Column("planned_start", sa.DateTime(), nullable=True),
        sa.Column("planned_end", sa.DateTime(), nullable=True),
        sa.Column("deadline", sa.DateTime(), nullable=True),
        sa.Column("delete_flag", sa.Boolean(), nullable=False),
        sa.Column("legacy_status", sa.String(), nullable=True),
        sa.Column("legacy_plan_item_id", sa.Integer(), nullable=False),
        sa.Column("legacy_version", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("issue_seq", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("kitting_no", "lot_no"),
    )
    op.create_index("ix_plans_line_status_start", "plans", ["line_code", "status", "planned_start"])

    op.create_table(
        "plan_sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("result", sa.String(), nullable=False),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("changed", sa.Integer(), nullable=False),
        sa.Column("unchanged", sa.Integer(), nullable=False),
        sa.Column("cancelled", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "plan_sync_warnings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=False),
        sa.Column("legacy_plan_item_id", sa.Integer(), nullable=True),
        sa.Column("kitting_no", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["sync_run_id"], ["plan_sync_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_sync_warnings_sync_run_id", "plan_sync_warnings", ["sync_run_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_sync_warnings_sync_run_id", table_name="plan_sync_warnings")
    op.drop_table("plan_sync_warnings")
    op.drop_table("plan_sync_runs")
    op.drop_index("ix_plans_line_status_start", table_name="plans")
    op.drop_table("plans")
