"""管理画面「管理表の内容」の Excel 取り込みのAPI。管理者のログインが要る。ルールは services/control_sheet_import.py。

ブックは本文にそのまま載せる(multipart にしない)。ブック名は filename に入れる。登録(apply)の本文は、先頭の 10 桁(10進数の文字)に続く
JSON(選んだファイルNo.の一覧。{"file_nos": [...]})の長さ、JSON、ブックの順。送ったブックはサーバーに残さない。
この2つのパスだけ、本文の上限を広げている(config.toml の [server] control_sheet_import_max_mb。app/main.py)。
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.admin import current_admin, require_header_for_writes
from app.db.models import Operator
from app.db.session import get_session
from app.services import control_sheet_import as service
from app.services.control_sheet_import import ImportHistoryOut, ImportPreviewOut, ImportResultOut
from app.services.errors import RuleViolation

router = APIRouter(prefix="/api/admin/control-sheets", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]
PREFIX_LENGTH = 10


def split_apply_body(body: bytes) -> tuple[list[str], bytes]:
    """登録の本文を、選んだファイルNo.の一覧とブックに分ける。"""
    head = body[:PREFIX_LENGTH]
    if len(head) != PREFIX_LENGTH or not head.isdigit():
        raise RuleViolation("送られたデータの形が違います")
    end = PREFIX_LENGTH + int(head)
    try:
        selected = json.loads(body[PREFIX_LENGTH:end].decode("utf-8"))["file_nos"]
    except (ValueError, KeyError, TypeError):
        raise RuleViolation("送られたデータの形が違います") from None
    if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
        raise RuleViolation("送られたデータの形が違います")
    return selected, body[end:]


@router.post("/import/preview", response_model=ImportPreviewOut)
async def preview_import(request: Request, _: Admin, session: Db, filename: str = Query(max_length=300)) -> ImportPreviewOut:
    """ブックを読んで、シートごとの結果を返す(確かめるだけ。DBには書かない)。本文はブックそのもの。"""
    data = await request.body()
    return await run_in_threadpool(service.preview, session, data, filename)


@router.post("/import/apply", response_model=ImportResultOut)
async def apply_import(request: Request, admin: Admin, session: Db, filename: str = Query(max_length=300)) -> ImportResultOut:
    """選んだファイルNo.を登録する(新規・変更ありのもの)。本文は、選んだ一覧とブック。"""
    selected, data = split_apply_body(await request.body())
    return await run_in_threadpool(service.apply_import, session, admin, data, filename, selected)


@router.get("/imports", response_model=list[ImportHistoryOut])
def import_history(_: Admin, session: Db) -> list[ImportHistoryOut]:
    """取り込みの履歴(誰が、いつ、どのブック名で、何件)。新しい順。"""
    return service.import_history(session)
