"""計画終了の履歴(plan_closures)

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-05

始まっていない計画を作業者が手で終わらせる(計画終了)と、その取り消しの履歴。行は消さず、追加するだけ。
詳細: docs/design/run-records.md(計画終了)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_closures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_plan_closures_kitting_lot", "plan_closures", ["kitting_no", "lot_no"])


def downgrade() -> None:
    op.drop_index("ix_plan_closures_kitting_lot", table_name="plan_closures")
    op.drop_table("plan_closures")
