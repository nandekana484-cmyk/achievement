"""引き継ぎの「移さない」の確定(kitting_handovers.decision)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-31

移す先の候補が無い実績のある計画を、管理者が「移さない」と確定できるようにする(移さないときは移す先が空)。
詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("kitting_handovers") as batch:
        batch.add_column(sa.Column("decision", sa.String(), nullable=False, server_default="moved"))
        batch.alter_column("new_kitting_no", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM kitting_handovers WHERE decision = 'declined'")
    with op.batch_alter_table("kitting_handovers") as batch:
        batch.alter_column("new_kitting_no", existing_type=sa.String(), nullable=False)
        batch.drop_column("decision")
