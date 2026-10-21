"""管理画面のログイン(パスワード・セッション・失敗の回数)と、変更の記録(audit_log)のテーブル。詳細: docs/design/admin.md"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class AdminCredential(Base):
    """管理者のパスワード(既存アプリには無いので本アプリで持つ)。平文は持たず、scrypt のハッシュだけを持つ。"""

    __tablename__ = "admin_credentials"

    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String)  # scrypt$n$r$p$<ソルト>$<ハッシュ>(domain/passwords.py)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime)


class AdminSession(Base):
    """ログイン中のセッション。Cookie の値そのものは持たず、SHA-256 のハッシュで持つ。"""

    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("operators.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime)


class AdminLoginAttempt(Base):
    """作業者IDごとの、続けて間違えた回数と、ログインできない期限(IDが無くても数える)。"""

    __tablename__ = "admin_login_attempts"

    worker_key: Mapped[str] = mapped_column(String, primary_key=True)  # 正規化した作業者ID
    failures: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(TZDateTime)


class AuditLog(Base):
    """変更の記録(誰が、いつ、何を、変更前と変更後)。マスタの変更と、今後の実績の訂正で使う。"""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    changed_at: Mapped[datetime] = mapped_column(TZDateTime)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("operators.id"))
    target_table: Mapped[str] = mapped_column(String)  # equipment / reasons / lines / operators / admin_credentials
    target_key: Mapped[str] = mapped_column(String)  # 対象の行(主キーを文字にしたもの)
    action: Mapped[str] = mapped_column(String)  # create / update
    before_json: Mapped[str | None] = mapped_column(Text)  # 変わった項目の変更前(作ったときは空)
    after_json: Mapped[str] = mapped_column(Text)  # 変わった項目の変更後
    reason: Mapped[str | None] = mapped_column(Text)  # 訂正の理由(実績の訂正で使う)

    __table_args__ = (Index("ix_audit_log_target", "target_table", "target_key"),)
