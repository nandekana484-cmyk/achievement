"""K社製品ロット管理票の、ファイルNo.ごとの内容(工程の行と管理No)の履歴。詳細: docs/design/control-sheet.md"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class ControlSheetVersion(Base):
    """ファイルNo.ごとの管理表の内容の版。保存のたびに版を1つ足す(行は消さず、更新もしない)。ファイルNo.ごとに、最後の版が今の内容。

    file_no は既存アプリの setup_file_no と同じ値(plans.file_no)。rows_json は工程の行の配列(名前・区分・作業要領など)。
    action: save=保存 / copy=別のファイルNo.の内容をコピーして新しく作った(copied_from がコピー元)/ import=Excel のブックから取り込んだ(import_id が取り込みの単位)。
    """

    __tablename__ = "control_sheet_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_no: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    manager_no: Mapped[str] = mapped_column(String, default="")
    rows_json: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String)
    copied_from: Mapped[str | None] = mapped_column(String)
    import_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("control_sheet_imports.id", name="fk_control_sheet_import"))
    saved_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    saved_at: Mapped[datetime] = mapped_column(TZDateTime)

    __table_args__ = (
        UniqueConstraint("file_no", "version", name="uq_control_sheet_file_version"),
        Index("ix_control_sheet_versions_file", "file_no"),
    )


class ControlSheetImport(Base):
    """Excel のブックからの取り込み1回(誰が、いつ、どのブック名で、何件)。行は消さず、追加するだけ。詳細: docs/design/control-sheet.md"""

    __tablename__ = "control_sheet_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String)
    imported_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    imported_at: Mapped[datetime] = mapped_column(TZDateTime)
    sheet_count: Mapped[int] = mapped_column(Integer)  # ブックのシートの数
    registered_count: Mapped[int] = mapped_column(Integer)  # 登録したファイルNo.の数
