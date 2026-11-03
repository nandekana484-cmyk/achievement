"""ロットへの割り振り(キッティングNo.ごとの生産数の合計を、ロットに分けた値)の保存の履歴。詳細: docs/design/actuals-export.md"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class LotAllocationChange(Base):
    """割り振りの保存・元に戻す・引き継ぎの履歴(行は消さず、追加するだけ)。キッティングNo.ごとに、最後の行が有効。

    action: save=保存 / reset=元に戻す(今の規則に戻る)/ handover_in=引き継ぎで移ってきた / handover_out=引き継ぎで移っていった。
    after_json は、その操作のあとの {ロットNo.: 数}(reset・handover_out は今の規則の値)。有効なのは、最後の行が save か handover_in のときだけ。
    """

    __tablename__ = "lot_allocation_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)  # field(現場の作業者)/ admin(管理者)
    changed_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    changed_at: Mapped[datetime] = mapped_column(TZDateTime)
    before_json: Mapped[str | None] = mapped_column(Text)  # 操作の前の {ロットNo.: 数}
    after_json: Mapped[str | None] = mapped_column(Text)
    exported_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # 変えたとき、書き出し済みだった計画の最後の書き出し日時
    export_checked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("operators.id", name="fk_lot_alloc_checked_by"))
    export_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (Index("ix_lot_allocation_changes_kitting", "kitting_no"),)
