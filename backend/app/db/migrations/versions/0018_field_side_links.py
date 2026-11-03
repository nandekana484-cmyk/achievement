"""現場での面1と面2の紐づけ(side_links を広げる)と、書き出した行の記録(exported_rows)

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-03

管理者が確定した紐づけの表 side_links に、操作(action)、した人の種類(source)、前の相手、書き出し済みだった日時、
管理者の確認済みを足す。古い行は action(つなぐ / つながない)と source=admin にする。
書き出した行は exported_rows に記録する(古い書き出しは、保存した CSV から作る)。詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("side_links") as batch:
        batch.add_column(sa.Column("action", sa.String(), nullable=False, server_default="link"))
        batch.add_column(sa.Column("source", sa.String(), nullable=False, server_default="admin"))
        batch.add_column(sa.Column("previous_partner", sa.String(), nullable=True))
        batch.add_column(sa.Column("exported_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("export_checked_by", sa.Integer(), sa.ForeignKey("operators.id", name="fk_side_links_checked_by"), nullable=True))
        batch.add_column(sa.Column("export_checked_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE side_links SET action = 'skip' WHERE side2_kitting_no IS NULL")
    op.create_index("ix_side_links_side2", "side_links", ["side2_kitting_no"])
    exported = op.create_table(
        "exported_rows",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("export_id", sa.Integer(), sa.ForeignKey("actuals_exports.id"), nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("side1_kitting_no", sa.String(), nullable=True),
    )
    op.create_index("ix_exported_rows_kitting", "exported_rows", ["kitting_no"])
    op.create_index("ix_exported_rows_side1", "exported_rows", ["side1_kitting_no"])
    _backfill(exported)


def _backfill(exported: sa.Table) -> None:
    """保存してある書き出しの CSV(見出しは日本語)から、書き出した行を作る。"""
    conn = op.get_bind()
    rows = []
    for export_id, content in conn.execute(sa.text("SELECT id, content FROM actuals_exports")):
        for r in csv.DictReader(io.StringIO(content, newline="")):
            kitting = (r.get("キッティングNo.") or "").strip()
            if kitting:
                rows.append({"export_id": export_id, "kitting_no": kitting, "lot_no": (r.get("ロットNo.") or "").strip(),
                             "side1_kitting_no": (r.get("面1のキッティングNo.") or "").strip() or None})
    if rows:
        op.bulk_insert(exported, rows)


def downgrade() -> None:
    op.drop_index("ix_exported_rows_side1", table_name="exported_rows")
    op.drop_index("ix_exported_rows_kitting", table_name="exported_rows")
    op.drop_table("exported_rows")
    op.drop_index("ix_side_links_side2", table_name="side_links")
    with op.batch_alter_table("side_links") as batch:
        batch.drop_column("export_checked_at")
        batch.drop_column("export_checked_by")
        batch.drop_column("exported_at")
        batch.drop_column("previous_partner")
        batch.drop_column("source")
        batch.drop_column("action")
