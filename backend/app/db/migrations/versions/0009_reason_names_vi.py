"""初期データの理由に、ベトナム語の名前を入れる(name_vi が空のときだけ。人が入れた値は上書きしない)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-21

訳はレビュー役が用意した初版。詳細: docs/design/i18n.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 0004 で入れた理由の名前 → ベトナム語の名前
REASON_NAMES_VI = {
    "部品探し": "Tìm linh kiện",
    "欠品": "Thiếu linh kiện",
    "マシントラブル": "Sự cố máy",
    "立上立会": "Tham gia khởi động",
    "応援・その他": "Hỗ trợ / Khác",
    "その他トラブル": "Sự cố khác",
    "人員交代": "Đổi người",
    "トラブル停止": "Dừng do sự cố",
    "計画切替": "Chuyển kế hoạch",
}


def upgrade() -> None:
    stmt = sa.text("UPDATE reasons SET name_vi = :vi WHERE name = :name AND (name_vi IS NULL OR TRIM(name_vi) = '')")
    for name, vi in REASON_NAMES_VI.items():
        op.execute(stmt.bindparams(name=name, vi=vi))


def downgrade() -> None:
    # ここで入れた値のままのものだけ空に戻す(人が変えた値は残す)
    stmt = sa.text("UPDATE reasons SET name_vi = NULL WHERE name = :name AND name_vi = :vi")
    for name, vi in REASON_NAMES_VI.items():
        op.execute(stmt.bindparams(name=name, vi=vi))
