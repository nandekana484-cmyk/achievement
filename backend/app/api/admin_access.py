"""管理画面の「アクセス制限」のAPI: 許可するIPアドレスの一覧、追加、無効化、今の接続元が許可されているか。

管理者のログインが要る。今の接続元が許可から外れる変更は 409。詳細: docs/design/security.md(アクセス制限)
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.db.models import AllowedNetwork, Operator
from app.db.session import get_session
from app.services import ip_allowlist

router = APIRouter(prefix="/api/admin/access", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


class AllowedNetworkOut(BaseModel):
    id: int
    network: str  # 正規化した範囲(1台は /32)
    scope: Literal["field", "admin"]
    note: str | None
    created_by: str | None  # 名前(作業者ID)。開発用コマンドで足したときは空
    created_at: dt.datetime
    active: bool
    disabled_at: dt.datetime | None
    disabled_by: str | None


class AccessOut(BaseModel):
    my_ip: str  # 今の接続元(TCP 接続の相手。IPv4 射影は IPv4 にしたもの)
    my_ip_is_loopback: bool  # サーバーのPC自身(常に許可)
    field_restricted: bool  # 現場用の一覧に有効な範囲がある
    admin_restricted: bool  # 管理画面用の一覧に有効な範囲がある(無ければ現場用と同じ)
    field_allowed: bool
    admin_allowed: bool
    networks: list[AllowedNetworkOut]


class AllowedNetworkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: str = Field(max_length=64, description="1台(192.168.3.5)か範囲(192.168.3.0/24)。IPv6 も可")
    scope: Literal["field", "admin"]
    note: str | None = Field(default=None, max_length=200)


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


def _row(session: Session, r: AllowedNetwork) -> AllowedNetworkOut:
    return AllowedNetworkOut(
        id=r.id, network=r.network, scope=r.scope, note=r.note, created_by=ip_allowlist.who(session, r.created_by),
        created_at=r.created_at, active=r.active, disabled_at=r.disabled_at, disabled_by=ip_allowlist.who(session, r.disabled_by),
    )


@router.get("", response_model=AccessOut)
def get_access(request: Request, _: Admin, session: Db) -> AccessOut:
    """許可するIPアドレスの一覧(無効にしたものも)と、今の接続元が許可されているか。"""
    st = ip_allowlist.status_of(ip_allowlist.load_lists(session), _client_host(request))
    return AccessOut(
        my_ip=st.my_ip, my_ip_is_loopback=st.loopback, field_restricted=st.field_restricted, admin_restricted=st.admin_restricted,
        field_allowed=st.field_allowed, admin_allowed=st.admin_allowed,
        networks=[_row(session, r) for r in ip_allowlist.list_rows(session)],
    )


@router.post("/networks", response_model=AllowedNetworkOut)
def add_network(request: Request, admin: Admin, session: Db, body: AllowedNetworkIn) -> AllowedNetworkOut:
    """範囲を追加する。書き方の誤り、同じ範囲、今の接続元が許可から外れる変更は 409。"""
    row = ip_allowlist.add_network(session, admin.id, body.network, body.scope, body.note, _client_host(request))
    return _row(session, row)


@router.post("/networks/{network_id}/disable", response_model=AllowedNetworkOut)
def disable_network(request: Request, admin: Admin, session: Db, network_id: int) -> AllowedNetworkOut:
    """範囲を無効にする(履歴は残す)。今の接続元が許可から外れる変更は 409。"""
    return _row(session, ip_allowlist.disable_network(session, admin.id, network_id, _client_host(request)))
