"""警告を同じ内容ごとに1件にまとめる形に変え、同期の記録に revived(取消から復活)を足す

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20

plan_sync_warnings は作り直す(sync_run_id を持たない形に変わるため)。それまでの警告は消える。
警告は同期のたびに出し直されるので、次の同期で今の状態に戻る。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("plan_sync_runs") as batch:
        batch.add_column(sa.Column("revived", sa.Integer(), nullable=False, server_default="0"))

    op.drop_index("ix_plan_sync_warnings_sync_run_id", table_name="plan_sync_warnings")
    op.drop_table("plan_sync_warnings")
    op.create_table(
        "plan_sync_warnings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=True),
        sa.Column("lot_no", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("legacy_plan_item_id", sa.Integer(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_sync_warnings_key", "plan_sync_warnings", ["kitting_no", "lot_no"])
    op.create_index("ix_plan_sync_warnings_resolved_at", "plan_sync_warnings", ["resolved_at"])


def downgrade() -> None:
    op.drop_index("ix_plan_sync_warnings_resolved_at", table_name="plan_sync_warnings")
    op.drop_index("ix_plan_sync_warnings_key", table_name="plan_sync_warnings")
    op.drop_table("plan_sync_warnings")
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

    with op.batch_alter_table("plan_sync_runs") as batch:
        batch.drop_column("revived")
