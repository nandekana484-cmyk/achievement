"""既存アプリのすべての月次DBを読む形に合わせ、計画に正とするDBと想定タクトを、同期の記録に読んだDBの一覧を足す

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

想定タクトは次の同期で入る(内容が変わったものとして数える)。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("plans") as batch:
        batch.add_column(sa.Column("takt_sec", sa.Float(), nullable=True))
        batch.add_column(sa.Column("source_db", sa.String(), nullable=True))
    with op.batch_alter_table("plan_sync_runs") as batch:
        batch.add_column(sa.Column("legacy_dbs", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_sync_runs") as batch:
        batch.drop_column("legacy_dbs")
    with op.batch_alter_table("plans") as batch:
        batch.drop_column("source_db")
        batch.drop_column("takt_sec")
