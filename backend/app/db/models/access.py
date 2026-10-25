"""アクセスを許可するIPアドレスの範囲(allowed_networks)。行は消さず、使わなくなったものは active=False にする。

詳細: docs/design/security.md(アクセス制限)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class AllowedNetwork(Base):
    __tablename__ = "allowed_networks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    network: Mapped[str] = mapped_column(String)  # 正規化した CIDR(192.168.3.0/24、1台なら 192.168.3.5/32、IPv6 も同じ形)
    scope: Mapped[str] = mapped_column(String)  # field(現場用)/ admin(管理画面用)
    note: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))  # 開発用コマンド(サーバーのPC)で足したときは空
    created_at: Mapped[datetime] = mapped_column(TZDateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    disabled_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    disabled_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))

    __table_args__ = (Index("ix_allowed_networks_active", "active", "scope"),)
