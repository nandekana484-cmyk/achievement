"""管理画面のログイン(パスワード・セッション・失敗の回数)と、変更の記録(audit_log)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-21

詳細: docs/design/admin.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_credentials",
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), primary_key=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.String(), primary_key=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_sessions_operator_id", "admin_sessions", ["operator_id"])
    op.create_table(
        "admin_login_attempts",
        sa.Column("worker_key", sa.String(), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=True),
        sa.Column("target_table", sa.String(), nullable=False),
        sa.Column("target_key", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_log_target", "audit_log", ["target_table", "target_key"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_target", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("admin_login_attempts")
    op.drop_index("ix_admin_sessions_operator_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("admin_credentials")
