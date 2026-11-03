"""ロットへの割り振りの保存(lot_allocation_changes)

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-03

キッティングNo.ごとの生産数の合計を、ロットに分けた値の保存・元に戻す・引き継ぎの履歴。行は消さず、追加するだけ。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lot_allocation_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("export_checked_by", sa.Integer(), sa.ForeignKey("operators.id", name="fk_lot_alloc_checked_by"), nullable=True),
        sa.Column("export_checked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_lot_allocation_changes_kitting", "lot_allocation_changes", ["kitting_no"])


def downgrade() -> None:
    op.drop_index("ix_lot_allocation_changes_kitting", table_name="lot_allocation_changes")
    op.drop_table("lot_allocation_changes")
