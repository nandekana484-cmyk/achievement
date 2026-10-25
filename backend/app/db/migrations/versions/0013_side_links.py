"""人が確定した、面1と面2の計画のひも付け(side_links)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-25

キッティングNo.(回を除いた部分)でつながらない面1を、管理者が面2の計画に確定する。履歴は消さない。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "side_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("side1_kitting_no", sa.String(), nullable=False),
        sa.Column("side2_kitting_no", sa.String(), nullable=True),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_side_links_side1", "side_links", ["side1_kitting_no", "lot_no"])


def downgrade() -> None:
    op.drop_index("ix_side_links_side1", table_name="side_links")
    op.drop_table("side_links")
