"""計画終了(始まっていない計画を、作業者が手で終わらせる)の履歴。詳細: docs/design/run-records.md(計画終了)"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class PlanClosure(Base):
    """計画終了と、その取り消しの履歴(1件ずつ足す。物理削除しない)。ロット(キッティングNo.、ロットNo.)ごとに、最後の行が今の状態。

    action: close=計画終了 / cancel=計画終了を取り消す。reason は close のときだけ(delay_stop / plan_change / other)。
    計画の取り込み(同期)で plans の行が変わっても消えない(plans とは別の表)。
    """

    __tablename__ = "plan_closures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    lot_no: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text)
    operator_id: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime)

    __table_args__ = (Index("ix_plan_closures_kitting_lot", "kitting_no", "lot_no"),)
