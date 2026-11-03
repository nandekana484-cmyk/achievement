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
    """面1と面2のひも付けの履歴(管理者と現場の作業者の両方。行は消さず、追加するだけ)。最後の行が有効。

    action: link=面1と面2をつなぐ / unlink=外す(キー H の自動のつなぎには戻る)/ skip=「つながない」(面1は書き出さない。管理者だけ)。
    キッティングNo.の組(lot_no が空)が現場の画面での紐づけ。古い行(管理者が確定したもの)は lot_no を持つが、組として同じに読む。
    読み方と優先順位(明示の紐づけはキー H より優先): docs/design/actuals-export.md
    """

    __tablename__ = "side_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_no: Mapped[str] = mapped_column(String)  # 現場の画面からの紐づけは空(キッティングNo.の組)
    side1_kitting_no: Mapped[str] = mapped_column(String)  # 面1の計画。外す(unlink)ときは、外した相手
    side2_kitting_no: Mapped[str | None] = mapped_column(String)  # 面2の計画(skip は空)
    decided_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    decided_at: Mapped[datetime] = mapped_column(TZDateTime)
    action: Mapped[str] = mapped_column(String, default="link", server_default="link")
    source: Mapped[str] = mapped_column(String, default="admin", server_default="admin")  # field / admin
    previous_partner: Mapped[str | None] = mapped_column(String)  # 変える前の相手(明示でもキー H でも、そのときの相手)
    exported_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # 変えたとき、書き出し済みだった計画の最後の書き出し日時
    export_checked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("operators.id", name="fk_side_links_checked_by"))
    export_checked_at: Mapped[datetime | None] = mapped_column(TZDateTime)  # 管理者が「確認済み」にした日時

    __table_args__ = (Index("ix_side_links_side1", "side1_kitting_no", "lot_no"), Index("ix_side_links_side2", "side2_kitting_no"))


class ExportedRow(Base):
    """書き出した行(どの書き出しに、どの計画が入ったか)。書き出し後の紐づけの変更を見つけるために使う。"""

    __tablename__ = "exported_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    export_id: Mapped[int] = mapped_column(Integer, ForeignKey("actuals_exports.id"))
    kitting_no: Mapped[str] = mapped_column(String)
    lot_no: Mapped[str] = mapped_column(String)
    side1_kitting_no: Mapped[str | None] = mapped_column(String)  # 面2の行でつながっていた面1

    __table_args__ = (Index("ix_exported_rows_kitting", "kitting_no"), Index("ix_exported_rows_side1", "side1_kitting_no"))
