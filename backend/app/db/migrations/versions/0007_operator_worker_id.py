"""作業者に、既存アプリの作業者ID・役割・取り込み元を足す(operators.worker_id / worker_key / role / source)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-21

それまでの作業者は、開発用コマンドで足したもの(source=local、作業者IDなし)とする。
表は作り直さず列を足す(工程の記録などが作業者を参照しているので、作り直すと外部キーで止まるため)。
一意にするのはユニークインデックスで行う。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("operators", sa.Column("worker_id", sa.String(), nullable=True))
    op.add_column("operators", sa.Column("worker_key", sa.String(), nullable=True))
    op.add_column("operators", sa.Column("role", sa.String(), nullable=False, server_default="operator"))
    op.add_column("operators", sa.Column("source", sa.String(), nullable=False, server_default="local"))
    op.create_index("ux_operators_worker_id", "operators", ["worker_id"], unique=True)
    op.create_index("ux_operators_worker_key", "operators", ["worker_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_operators_worker_key", table_name="operators")
    op.drop_index("ux_operators_worker_id", table_name="operators")
    for column in ("source", "role", "worker_key", "worker_id"):
        op.drop_column("operators", column)
