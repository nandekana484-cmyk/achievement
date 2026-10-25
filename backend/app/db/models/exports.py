"""実績の書き出し(既存アプリに戻すための CSV)の履歴と、人が確定した面1と面2のひも付けのテーブル。詳細: docs/design/actuals-export.md"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class ActualsExport(Base):
    """書き出し1回分(いつ・誰が・何行・ファイル名)。書き出しても実績の記録は変えない。"""

    __tablename__ = "actuals_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exported_at: Mapped[datetime] = mapped_column(TZDateTime)
    exported_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    row_count: Mapped[int] = mapped_column(Integer)
    file_name: Mapped[str] = mapped_column(String)  # exchange_dir\actuals\ の中のファイル名
    date_from: Mapped[date] = mapped_column(Date)  # 絞り込みの期間(稼働日)
    date_to: Mapped[date] = mapped_column(Date)
    line_code: Mapped[str | None] = mapped_column(String)  # 絞り込みのライン(空はすべて)
    content: Mapped[str] = mapped_column(Text)  # 書き出した CSV(BOM を除いた文字列)。画面からのダウンロードに使う


class SideLink(Base):
    """人が確定した、面1の計画と面2の計画のひも付け(キッティングNo.でつながらなかったもの)。

    面2を空にした行は「つながない(面1は書き出さない)」。やり直しは新しい行を足し、同じ面1の最新の行を使う(履歴は消さない)。
    """

    __tablename__ = "side_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_no: Mapped[str] = mapped_column(String)
    side1_kitting_no: Mapped[str] = mapped_column(String)  # 面1の計画(キッティングNo.+ロットNo.)
    side2_kitting_no: Mapped[str | None] = mapped_column(String)  # 面2の計画(同じロットNo.)。空は「つながない」
    decided_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    decided_at: Mapped[datetime] = mapped_column(TZDateTime)

    __table_args__ = (Index("ix_side_links_side1", "side1_kitting_no", "lot_no"),)
