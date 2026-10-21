"""マスタ(ライン・作業者・設備・理由)のテーブル。行は消さず、使わなくなったものは active=False にする。"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Line(Base):
    """ライン。計画の同期で新しいラインの記号を見つけたら自動で登録する。"""

    __tablename__ = "lines"

    line_code: Mapped[str] = mapped_column(String, primary_key=True)  # 正規化した値
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Operator(Base):
    """作業者。既存アプリの master.db の workers から読み込む(source=legacy)か、開発用コマンドで足す(source=local)。"""

    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String)  # 作業者ID(既存アプリの表記のまま)
    worker_key: Mapped[str | None] = mapped_column(String)  # 作業者IDを正規化した値(呼び出しと重複の判定に使う)
    role: Mapped[str] = mapped_column(String, default="operator")  # admin / operator
    source: Mapped[str] = mapped_column(String, default="local")  # legacy / local

    __table_args__ = (
        Index("ux_operators_worker_id", "worker_id", unique=True),
        Index("ux_operators_worker_key", "worker_key", unique=True),
    )


class Equipment(Base):
    """設備(ラインごと)。"""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_code: Mapped[str] = mapped_column(String, ForeignKey("lines.line_code"))
    name: Mapped[str] = mapped_column(String)
    name_vi: Mapped[str | None] = mapped_column(String)  # ベトナム語の名前。空なら画面は日本語の名前を出す
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Reason(Base):
    """理由(付帯作業の種類と、生産の再開理由の共通マスタ。開発指針 5.5)。"""

    __tablename__ = "reasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    name_vi: Mapped[str | None] = mapped_column(String)  # ベトナム語の名前。空なら画面は日本語の名前を出す
    category: Mapped[str] = mapped_column(String)  # loss=ロス / non_loss=ロス以外
    # TODO(要確認): 付帯作業を稼働率に含めるか(今はすべて含めない)
    counts_in_utilization: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_equipment: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_text: Mapped[bool] = mapped_column(Boolean, default=False)
    usable_as_line_event: Mapped[bool] = mapped_column(Boolean, default=False)  # 付帯作業として使える
    usable_as_restart: Mapped[bool] = mapped_column(Boolean, default=False)  # 生産の再開理由として使える
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
