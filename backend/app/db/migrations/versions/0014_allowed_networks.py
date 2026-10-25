"""アクセスを許可するIPアドレスの範囲(allowed_networks)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-25

詳細: docs/design/security.md(アクセス制限)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "allowed_networks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("network", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("disabled_at", sa.DateTime(), nullable=True),
        sa.Column("disabled_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=True),
    )
    op.create_index("ix_allowed_networks_active", "allowed_networks", ["active", "scope"])


def downgrade() -> None:
    op.drop_index("ix_allowed_networks_active", table_name="allowed_networks")
    op.drop_table("allowed_networks")
