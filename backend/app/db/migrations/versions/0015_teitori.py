"""丁取りの写し(board_teitori)と、完了の写しの丁取り数

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-31

既存アプリの master.db のビュー v_board_teitori を、計画の同期のたびに上書きして持つ。
片付けの完了時に、丁取り数と status を完了の写しに残す。詳細: docs/design/metrics.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "board_teitori",
        sa.Column("setup_file_no", sa.String(), nullable=False),
        sa.Column("mounting_line", sa.String(), nullable=False),
        sa.Column("teitori", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("part_no", sa.String(), nullable=True),
        sa.Column("fetched_at", sa.String(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("setup_file_no", "mounting_line"),
    )
    with op.batch_alter_table("run_completions") as batch:
        batch.add_column(sa.Column("teitori_snapshot", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("teitori_status_snapshot", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_completions") as batch:
        batch.drop_column("teitori_status_snapshot")
        batch.drop_column("teitori_snapshot")
    op.drop_table("board_teitori")
