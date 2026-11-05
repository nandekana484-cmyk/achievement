"""K社製品ロット管理票の、ファイルNo.ごとの内容の履歴(control_sheet_versions)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-06

ファイルNo.ごとの管理No・工程の行(作業要領など)を、保存のたびに版として足す。行は消さず、更新もしない。
詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "control_sheet_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_no", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("manager_no", sa.String(), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("copied_from", sa.String(), nullable=True),
        sa.Column("saved_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("file_no", "version", name="uq_control_sheet_file_version"),
    )
    op.create_index("ix_control_sheet_versions_file", "control_sheet_versions", ["file_no"])


def downgrade() -> None:
    op.drop_index("ix_control_sheet_versions_file", table_name="control_sheet_versions")
    op.drop_table("control_sheet_versions")
