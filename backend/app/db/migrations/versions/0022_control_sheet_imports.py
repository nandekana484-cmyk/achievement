"""管理表の内容の Excel 取り込みの履歴(control_sheet_imports)と、版に取り込みの印(import_id)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-06

取り込み1回(誰が、いつ、どのブック名で、何件)を表に足し、取り込みで作った版に import_id を付ける。行は消さず、追加するだけ。
詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "control_sheet_imports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("imported_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("sheet_count", sa.Integer(), nullable=False),
        sa.Column("registered_count", sa.Integer(), nullable=False),
    )
    with op.batch_alter_table("control_sheet_versions") as batch:  # SQLite は、あとから外部キーを足せない(バッチで作り直す)
        batch.add_column(sa.Column("import_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_control_sheet_import", "control_sheet_imports", ["import_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("control_sheet_versions") as batch:
        batch.drop_constraint("fk_control_sheet_import", type_="foreignkey")
        batch.drop_column("import_id")
    op.drop_table("control_sheet_imports")
