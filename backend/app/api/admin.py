"""管理画面のAPI: ログイン・ログアウト・自分の情報・パスワードの変更。マスタの管理は admin_masters.py。

/api/admin/ の下は、すべてサーバーでセッションと管理者であることを確かめる(ログインを除く)。
データを変える要求は、Cookie に加えて決まったヘッダー(X-Genba-Admin: 1)が無ければ断る。詳細: docs/design/admin.md
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_config
from app.db.models import Operator
from app.db.session import get_session
from app.services import admin_auth
from app.services.errors import Forbidden

COOKIE = "genba_admin"
COOKIE_PATH = "/api/admin"
WRITE_HEADER = "X-Genba-Admin"


def require_header_for_writes(request: Request) -> None:
    """データを変える要求には、決まったヘッダーを求める(別のサイトのページからの送信を防ぐため)。"""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(WRITE_HEADER) != "1":
        raise Forbidden(f"この操作には {WRITE_HEADER} ヘッダーが必要です")


def current_admin(request: Request, session: Session = Depends(get_session)) -> Operator:
    """ログイン中の管理者(セッションが無い・切れた・管理者でなくなったら 401)。"""
    return admin_auth.authenticate(session, request.cookies.get(COOKIE), get_config().admin)


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_header_for_writes)])


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(_Body):
    worker_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class PasswordChangeIn(_Body):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class AdminMeOut(BaseModel):
    operator_id: int
    worker_id: str | None
    name: str
    idle_minutes: int  # 操作が無いとログインが切れるまでの分
    server_time: dt.datetime
    workday: dt.date  # サーバーの今の稼働日(8:15 より前なら前の日)。日報や CSV の日付の初期値に使う


def _me(op: Operator) -> AdminMeOut:
    from app.core import clock
    from app.domain.workday import workday_of

    now = clock.now()
    return AdminMeOut(operator_id=op.id, worker_id=op.worker_id, name=op.name,
                      idle_minutes=get_config().admin.idle_minutes, server_time=now,
                      workday=workday_of(now, get_config().schedule.day_start))


@router.post("/login", response_model=AdminMeOut)
def login(body: LoginIn, request: Request, response: Response, session: Session = Depends(get_session)) -> AdminMeOut:
    """作業者IDとパスワードでログインする。失敗の理由は区別しない(401「作業者IDかパスワードが違います」)。"""
    token, op = admin_auth.login(session, body.worker_id, body.password, get_config().admin,
                                 request.client.host if request.client else "unknown")
    # 社内LANの HTTP で使うので Secure は付けない(docs/design/admin.md)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path=COOKIE_PATH)
    return _me(op)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> None:
    """ログアウトする(ログインしていなくてもよい)。"""
    admin_auth.logout(session, request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path=COOKIE_PATH)


@router.get("/me", response_model=AdminMeOut)
def me(op: Operator = Depends(current_admin)) -> AdminMeOut:
    """ログイン中の管理者(ログインしていなければ 401)。"""
    return _me(op)


@router.put("/password", status_code=204)
def change_password(body: PasswordChangeIn, request: Request, op: Operator = Depends(current_admin),
                    session: Session = Depends(get_session)) -> None:
    """自分のパスワードを変える(今のパスワードが要る。8文字以上)。ほかのセッションは無効になる。"""
    admin_auth.change_own_password(session, op, body.current_password, body.new_password, request.cookies.get(COOKIE))
