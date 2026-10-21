"""理由と設備に、ベトナム語の名前を足す(reasons.name_vi / equipment.name_vi。空を許す)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-21

画面は選んだ言語の名前を出し、ベトナム語の名前が空なら日本語の名前を出す。詳細: docs/design/i18n.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reasons", sa.Column("name_vi", sa.String(), nullable=True))
    op.add_column("equipment", sa.Column("name_vi", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("equipment", "name_vi")
    op.drop_column("reasons", "name_vi")
