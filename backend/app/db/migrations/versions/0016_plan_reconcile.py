"""計画の取消の理由・古い計画の判定、実績の引き継ぎの履歴(kitting_handovers)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-31

plans に取消の理由(cancel_reason)と、既存アプリのビュー v_plan_stale の判定(is_stale、replacement_*)を持つ。
前のアプリで取り消した計画の理由は「読めなくなった」(vanished)にする。詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("plans") as batch:
        batch.add_column(sa.Column("cancel_reason", sa.String(), nullable=True))
        batch.add_column(sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        batch.add_column(sa.Column("replacement_kitting_no", sa.String(), nullable=True))
        batch.add_column(sa.Column("replacement_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.execute("UPDATE plans SET cancel_reason = 'vanished' WHERE status = 'cancelled'")
    op.create_table(
        "kitting_handovers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("old_kitting_no", sa.String(), nullable=False),
        sa.Column("new_kitting_no", sa.String(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.Column("moved_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_kitting_handovers_old", "kitting_handovers", ["old_kitting_no"])


def downgrade() -> None:
    op.drop_index("ix_kitting_handovers_old", table_name="kitting_handovers")
    op.drop_table("kitting_handovers")
    with op.batch_alter_table("plans") as batch:
        batch.drop_column("replacement_count")
        batch.drop_column("replacement_kitting_no")
        batch.drop_column("is_stale")
        batch.drop_column("cancel_reason")
