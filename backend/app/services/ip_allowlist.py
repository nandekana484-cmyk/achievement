"""アクセスを許可するIPアドレス: 判定に使う一覧の読み込み(短い間だけ覚える)と、登録・無効化。

登録と無効化は、今の接続元が許可から外れるなら受け付けない(自分を締め出さないため)。履歴は消さず、無効にする。
詳細: docs/design/security.md(アクセス制限)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import AllowedNetwork, Operator
from app.db.session import get_sessionmaker, write_transaction
from app.domain.networks import (
    SCOPE_ADMIN,
    SCOPE_FIELD,
    SCOPE_LABELS,
    SCOPES,
    AccessLists,
    IpAddress,
    Network,
    is_allowed,
    is_loopback,
    parse_ip,
    parse_network,
)
from app.services.audit import record_change
from app.services.errors import NotFound, RuleViolation

logger = logging.getLogger(__name__)

CACHE_SECONDS = 5.0  # 別のプロセス(開発用コマンド)での変更が、この時間で反映される


def lists_from_rows(rows: list[AllowedNetwork]) -> AccessLists:
    nets: dict[str, list[Network]] = {SCOPE_FIELD: [], SCOPE_ADMIN: []}
    for r in rows:
        if not r.active or r.scope not in nets:
            continue
        try:
            nets[r.scope].append(parse_network(r.network))
        except ValueError:
            logger.error("アクセス制限の範囲を読めません(番号 %s)。この行は使いません", r.id)
    return AccessLists(field=tuple(nets[SCOPE_FIELD]), admin=tuple(nets[SCOPE_ADMIN]))


def load_lists(session: Session) -> AccessLists:
    return lists_from_rows(list(session.scalars(select(AllowedNetwork).where(AllowedNetwork.active.is_(True)))))


class _Cache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._value: AccessLists | None = None
        self._loaded_at = 0.0

    def get(self) -> AccessLists:
        """一覧(短い間は覚えている)。DBを読めないときは、前に読んだ一覧を使う。

        一度も読めていないときは、制限する側に倒す(サーバーのPC自身以外は断る)。1秒後に読み直す。
        """
        with self._lock:
            if self._value is not None and time.monotonic() - self._loaded_at < CACHE_SECONDS:
                return self._value
            try:
                with get_sessionmaker()() as session:
                    self._value = load_lists(session)
                self._loaded_at = time.monotonic()
            except Exception:  # noqa: BLE001  制限の確認でアプリ全体を止めない
                self._retry_soon()
            return self._value

    def _retry_soon(self) -> None:
        if self._value is None or self._value.unavailable:
            logger.exception("アクセス制限の一覧を、まだ一度も読めていません。制限する側に倒し、サーバーのPC自身以外は断ります(1秒後に読み直します)")
            self._value = AccessLists(unavailable=True)
        else:
            logger.exception("アクセス制限の一覧を読めませんでした。前に読んだ一覧を使います(1秒後に読み直します)")
        self._loaded_at = time.monotonic() - CACHE_SECONDS + 1

    def invalidate(self) -> None:
        """次の判定で読み直させる(読み直しに失敗したときのために、前の一覧は残す)。"""
        with self._lock:
            self._loaded_at = 0.0

    def reset(self) -> None:
        """前の一覧も捨てる(テスト用。起動直後の、まだ一度も読めていない状態に戻す)。"""
        with self._lock:
            self._value, self._loaded_at = None, 0.0


cache = _Cache()


@dataclass(frozen=True)
class AccessStatus:
    my_ip: str
    loopback: bool
    field_restricted: bool
    admin_restricted: bool
    field_allowed: bool
    admin_allowed: bool


def status_of(lists: AccessLists, client_host: str | None) -> AccessStatus:
    ip = parse_ip(client_host)
    return AccessStatus(
        my_ip=str(ip) if ip else (client_host or ""), loopback=is_loopback(ip),
        field_restricted=lists.field_restricted, admin_restricted=lists.admin_restricted,
        field_allowed=is_allowed(lists, ip, SCOPE_FIELD), admin_allowed=is_allowed(lists, ip, SCOPE_ADMIN),
    )


def list_rows(session: Session) -> list[AllowedNetwork]:
    """すべての行(有効なものが先、新しい順)。"""
    return list(session.scalars(select(AllowedNetwork).order_by(AllowedNetwork.active.desc(), AllowedNetwork.id.desc())))


def _check_scope(scope: str) -> None:
    if scope not in SCOPES:
        raise RuleViolation("区分は、現場用か管理画面用を選んでください")


def _lockout_message(ip: IpAddress, adding: bool) -> str:
    if adding:
        return (f"この変更をすると、今の接続元({ip})が許可されなくなり、管理画面に入れなくなります。"
                "今の接続元を含む範囲を、先に(または一緒に)登録してください")
    return (f"この範囲を無効にすると、今の接続元({ip})が許可されなくなり、管理画面に入れなくなります。"
            "今の接続元を許可する別の範囲を、先に登録してください")


def _check_not_locking_out(after: AccessLists, client_host: str | None, adding: bool) -> None:
    ip = parse_ip(client_host)
    if ip is not None and not is_allowed(after, ip, SCOPE_ADMIN):
        raise RuleViolation(_lockout_message(ip, adding))


def add_network(session: Session, actor_id: int | None, network: str, scope: str, note: str | None,
                client_host: str | None = None) -> AllowedNetwork:
    """範囲を登録する。同じ範囲が有効なら 409。今の接続元(client_host)が許可から外れるなら 409。"""
    _check_scope(scope)
    try:
        net = parse_network(network)
    except ValueError as e:
        raise RuleViolation(str(e)) from None
    with write_transaction(session):
        rows = list_rows(session)
        if any(r.active and r.scope == scope and parse_network(r.network) == net for r in rows):
            session.rollback()
            raise RuleViolation(f"すでに登録されています({SCOPE_LABELS[scope]} {net})")
        row = AllowedNetwork(network=str(net), scope=scope, note=(note or "").strip() or None, created_by=actor_id,
                             created_at=clock.now(), active=True)
        after = lists_from_rows([*rows, row])
        try:
            _check_not_locking_out(after, client_host, adding=True)
        except RuleViolation:
            session.rollback()
            raise
        session.add(row)
        session.flush()
        record_change(session, actor_id, "allowed_networks", str(row.id), "create", None,
                      {"network": row.network, "scope": row.scope, "note": row.note})
        session.commit()
    cache.invalidate()
    return row


def disable_network(session: Session, actor_id: int | None, network_id: int, client_host: str | None = None) -> AllowedNetwork:
    """範囲を無効にする(履歴は残す)。今の接続元が許可から外れるなら 409。すでに無効なら、そのまま返す。"""
    with write_transaction(session):
        row = session.get(AllowedNetwork, network_id)
        if row is None:
            session.rollback()
            raise NotFound(f"アクセス制限の範囲(番号 {network_id})が見つかりません")
        if not row.active:
            session.rollback()
            return row
        after = lists_from_rows([r for r in list_rows(session) if r.id != row.id])
        try:
            _check_not_locking_out(after, client_host, adding=False)
        except RuleViolation:
            session.rollback()
            raise
        _disable(session, row, actor_id, clock.now())
        session.commit()
    cache.invalidate()
    return row


def _disable(session: Session, row: AllowedNetwork, actor_id: int | None, now: datetime) -> None:
    row.active, row.disabled_at, row.disabled_by = False, now, actor_id
    record_change(session, actor_id, "allowed_networks", str(row.id), "update", {"active": True}, {"active": False})


def disable_all(session: Session, actor_id: int | None = None) -> int:
    """有効な範囲をすべて無効にする(制限がなくなる)。緊急用。無効にした件数を返す。"""
    with write_transaction(session):
        rows = [r for r in list_rows(session) if r.active]
        now = clock.now()
        for r in rows:
            _disable(session, r, actor_id, now)
        session.commit()
    cache.invalidate()
    return len(rows)


def who(session: Session, operator_id: int | None) -> str | None:
    op = session.get(Operator, operator_id) if operator_id is not None else None
    if op is None:
        return None
    return f"{op.name}({op.worker_id})" if op.worker_id else op.name


def log_access_restriction() -> None:
    """起動時のログ: アクセス制限が有効か、件数はいくつか。"""
    lists = cache.get()
    if lists.unavailable:
        logger.error("アクセス制限: 一覧を読めません。サーバーのPC自身以外は断っています")
        return
    if not lists.field and not lists.admin:
        logger.info("アクセス制限: 無効(すべての接続元を許可しています)")
        return
    logger.info("アクセス制限: 有効(現場用 %d件、管理画面用 %d件。管理画面用が空なら現場用と同じ。127.0.0.1 と ::1 は常に許可)",
                len(lists.field), len(lists.admin))
