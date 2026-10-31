"""実績の引き継ぎ(出し直しでキッティングNo.が変わった計画へ、実績を移した)の履歴。行は消さない。

詳細: docs/design/legacy-integration.md(実績の引き継ぎ)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class KittingHandover(Base):
    """管理者が確定した引き継ぎ1件。同じ古いキッティングNo.の行があれば引き継ぎ済み。"""

    __tablename__ = "kitting_handovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    old_kitting_no: Mapped[str] = mapped_column(String)
    new_kitting_no: Mapped[str | None] = mapped_column(String)  # 「移さない」と確定したときは空
    decision: Mapped[str] = mapped_column(String, default="moved", server_default="moved")  # moved / declined(移さない)
    confirmed_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    confirmed_at: Mapped[datetime] = mapped_column(TZDateTime)
    moved_json: Mapped[str] = mapped_column(Text)  # JSON: 表ごとの移した行数
    warnings_json: Mapped[str] = mapped_column(Text)  # JSON: 確定のときの警告

    __table_args__ = (Index("ix_kitting_handovers_old", "old_kitting_no"),)
