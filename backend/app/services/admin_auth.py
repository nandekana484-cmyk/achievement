"""管理画面のログイン・セッション・パスワード(開発指針 7.2、9)。詳細: docs/design/admin.md

- 管理画面に入れるのは、operators のうち role=admin で有効な作業者だけ。ログイン中でも、確認のたびに見直す
- 失敗の理由は区別しない(作業者IDが無いのか、パスワードが違うのか)。作業者IDごとに、続けて間違えたら一定時間止める
- セッションの値は Cookie で渡し、サーバーには SHA-256 のハッシュだけを持つ
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import AdminConfig
from app.db.models import AdminCredential, AdminLoginAttempt, AdminSession, Operator
from app.db.session import write_transaction
from app.domain.passwords import DUMMY_HASH, check_new_password, hash_password, needs_rehash, verify_password
from app.domain.worker_id import worker_key
from app.services.audit import record_change
from app.services.login_throttle import ip_throttle
from app.services.errors import NotFound, RuleViolation, TooManyAttempts, Unauthorized

LOGIN_FAILED = "作業者IDかパスワードが違います"
LOGIN_REQUIRED = "ログインしてください"
SESSION_EXPIRED = "ログインの有効期限が切れました。もう一度ログインしてください"
NOT_ADMIN = "管理画面を使う権限がありません"
_TOUCH_EVERY = timedelta(seconds=60)  # 操作のたびに書かないよう、最後の操作の時刻はこの間隔で書く


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_admin(op: Operator | None) -> bool:
    return op is not None and op.active and op.role == "admin"


def _find_admin(session: Session, worker_id: str) -> Operator | None:
    key = worker_key(worker_id)
    op = session.scalars(select(Operator).where(Operator.worker_key == key)).first() if key else None
    return op if is_admin(op) else None


def login(session: Session, worker_id: str, password: str, cfg: AdminConfig, ip: str = "unknown") -> tuple[str, Operator]:
    """ログインし、Cookie に入れるセッションの値と管理者を返す。作業者IDごとと、接続元(ip)ごとに失敗を数える。"""
    ip_throttle.check(ip)
    key = worker_key(worker_id) or "(空)"
    now = clock.now()
    attempt = session.get(AdminLoginAttempt, key)
    if attempt is not None and attempt.locked_until is not None and attempt.locked_until > now:
        minutes = max(1, int((attempt.locked_until - now).total_seconds() // 60) + 1)
        raise TooManyAttempts(f"続けて間違えたため、しばらくログインできません(あと約{minutes}分)")

    op = _find_admin(session, worker_id)
    cred = session.get(AdminCredential, op.id) if op is not None else None
    # ハッシュの確かめ(時間がかかる)は書き込みのロックの外で行う。IDが無くても同じだけ時間をかける
    ok = verify_password(password, cred.password_hash if cred is not None else DUMMY_HASH) and cred is not None

    # 古い(弱い)ハッシュは、パスワードが合ったときに今の強さで作り直す。時間がかかるので、これもロックの外で計算する
    upgraded = hash_password(password) if ok and needs_rehash(cred.password_hash) else None

    with write_transaction(session):
        attempt = session.get(AdminLoginAttempt, key) or AdminLoginAttempt(worker_key=key, failures=0)
        session.add(attempt)
        if not ok:
            attempt.failures += 1
            if attempt.failures >= cfg.lockout_failures:
                attempt.failures, attempt.locked_until = 0, now + timedelta(minutes=cfg.lockout_minutes)
            session.commit()
            ip_throttle.failed(ip, cfg)
            raise Unauthorized(LOGIN_FAILED)
        ip_throttle.succeeded(ip)
        if upgraded is not None:
            session.get(AdminCredential, op.id).password_hash = upgraded
        attempt.failures, attempt.locked_until = 0, None
        session.execute(delete(AdminSession).where(AdminSession.created_at < now - timedelta(hours=cfg.max_hours)))
        token = secrets.token_urlsafe(32)
        session.add(AdminSession(token_hash=_token_hash(token), operator_id=op.id, created_at=now, last_seen_at=now))
        session.commit()
    return token, op


def logout(session: Session, token: str | None) -> None:
    if not token:
        return
    with write_transaction(session):
        session.execute(delete(AdminSession).where(AdminSession.token_hash == _token_hash(token)))
        session.commit()


def authenticate(session: Session, token: str | None, cfg: AdminConfig) -> Operator:
    """セッションを確かめ、管理者を返す。切れている・管理者でなくなったら Unauthorized(セッションは消す)。"""
    if not token:
        raise Unauthorized(LOGIN_REQUIRED)
    row = session.get(AdminSession, _token_hash(token))
    if row is None:
        raise Unauthorized(LOGIN_REQUIRED)
    now = clock.now()
    op = session.get(Operator, row.operator_id)
    reason = _expired(row, now, cfg) or (None if is_admin(op) else NOT_ADMIN)
    if reason is not None:
        _end(session, row.token_hash)
        raise Unauthorized(reason)
    if now - row.last_seen_at >= _TOUCH_EVERY:
        with write_transaction(session):
            row = session.get(AdminSession, _token_hash(token))
            if row is not None:
                row.last_seen_at = now
            session.commit()
    return op


def _expired(row: AdminSession, now: datetime, cfg: AdminConfig) -> str | None:
    if now - row.last_seen_at > timedelta(minutes=cfg.idle_minutes) or now - row.created_at > timedelta(hours=cfg.max_hours):
        return SESSION_EXPIRED
    return None


def _end(session: Session, token_hash: str) -> None:
    with write_transaction(session):
        session.execute(delete(AdminSession).where(AdminSession.token_hash == token_hash))
        session.commit()


def set_password(session: Session, worker_id: str, password: str, actor_id: int | None = None) -> Operator:
    """管理者のパスワードを設定する(最初の設定とリセット。開発用コマンドから)。失敗の回数も戻す。"""
    problem = check_new_password(password)
    if problem:
        raise RuleViolation(problem)
    op = admin_for_password(session, worker_id)
    _store(session, op, password, actor_id)
    return op


def admin_for_password(session: Session, worker_id: str) -> Operator:
    """パスワードを設定できる管理者(有効で、役割が admin)。開発用コマンドは、パスワードを聞く前にこれで確かめる。"""
    op = session.scalars(select(Operator).where(Operator.worker_key == worker_key(worker_id))).first()
    if op is None:
        raise NotFound(f"作業者ID「{worker_id}」が見つかりません")
    if not is_admin(op):
        raise RuleViolation(f"作業者ID「{worker_id}」は、有効な管理者(既存アプリの役割が admin)ではありません")
    return op


def change_own_password(session: Session, op: Operator, current: str, new: str, keep_token: str | None = None) -> None:
    """管理画面から、自分のパスワードを変える(今のパスワードが要る)。変えた画面のセッション(keep_token)以外は無効にする。"""
    cred = session.get(AdminCredential, op.id)
    if cred is None or not verify_password(current, cred.password_hash):
        raise RuleViolation("今のパスワードが違います")
    problem = check_new_password(new)
    if problem:
        raise RuleViolation(problem)
    _store(session, op, new, op.id, _token_hash(keep_token) if keep_token else None)


def _store(session: Session, op: Operator, password: str, actor_id: int | None, keep_session: str | None = None) -> None:
    """パスワードを保存し、その人の既存のセッションを無効にする(keep_session のハッシュのものだけ残す。S-08)。"""
    hashed = hash_password(password)  # 時間がかかるので、ロックの外で計算する
    with write_transaction(session):
        cred = session.get(AdminCredential, op.id)
        action = "update" if cred is not None else "create"
        if cred is None:
            cred = AdminCredential(operator_id=op.id)
            session.add(cred)
        cred.password_hash, cred.updated_at = hashed, clock.now()
        session.execute(delete(AdminLoginAttempt).where(AdminLoginAttempt.worker_key == op.worker_key))
        others = delete(AdminSession).where(AdminSession.operator_id == op.id)
        session.execute(others.where(AdminSession.token_hash != keep_session) if keep_session else others)
        # パスワードそのものは記録しない
        record_change(session, actor_id, "admin_credentials", str(op.id), action, None, {"password": "(変更)"})
        session.commit()


def has_password(session: Session, operator_id: int) -> bool:
    return session.get(AdminCredential, operator_id) is not None
