"""実績の書き出しの履歴(actuals_exports)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-23

詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "actuals_exports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("exported_at", sa.DateTime(), nullable=False),
        sa.Column("exported_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("line_code", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("actuals_exports")
