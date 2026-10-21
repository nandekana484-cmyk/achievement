"""工程の記録に、再開理由の設備(run_events.equipment_id)を足す

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_events") as batch:
        batch.add_column(sa.Column("equipment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_run_events_equipment_id", "equipment", ["equipment_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("run_events") as batch:
        batch.drop_constraint("fk_run_events_equipment_id", type_="foreignkey")
        batch.drop_column("equipment_id")
