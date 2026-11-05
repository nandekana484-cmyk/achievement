"""管理画面の「管理表の内容」のAPI(K社製品ロット管理票のファイルNo.ごとの内容)。管理者のログインが要る。ルールは services/control_sheets.py。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.db.models import Operator
from app.db.session import get_session
from app.services import control_sheets
from app.services.control_sheets import ControlRow, ControlSheetOut, ControlSheetSummaryOut
from app.services.errors import NotFound

router = APIRouter(prefix="/api/admin/control-sheets", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


class SaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manager_no: str = Field(default="", max_length=50, description="管理No(文字。ファイルNo.ごと)")
    rows: list[ControlRow] = Field(description="工程の行(上から順。行の番号は印刷のときに1から振る)")


class CopyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file_no: str = Field(max_length=20, description="コピー元のファイルNo.(登録済み)")


@router.get("", response_model=list[ControlSheetSummaryOut])
def list_sheets(_: Admin, session: Db) -> list[ControlSheetSummaryOut]:
    """登録済みのファイルNo.(最後に直した人と日時つき)と、今の計画にあって未登録のファイルNo.。"""
    return control_sheets.list_sheets(session)


@router.get("/{file_no}", response_model=ControlSheetOut)
def get_sheet(file_no: str, _: Admin, session: Db) -> ControlSheetOut:
    """ファイルNo.の今の内容(未登録なら 404)。"""
    cur = control_sheets.get_current(session, file_no)
    if cur is None:
        raise NotFound(f"ファイルNo.({file_no})の管理表の内容は未登録です")
    return cur


@router.put("/{file_no}", response_model=ControlSheetOut)
def save_sheet(file_no: str, body: SaveIn, admin: Admin, session: Db) -> ControlSheetOut:
    """内容を保存する(新しい版を足す。未登録なら新しく作る)。"""
    return control_sheets.save(session, admin, file_no, body.manager_no, body.rows)


@router.post("/{file_no}/copy", response_model=ControlSheetOut)
def copy_sheet(file_no: str, body: CopyIn, admin: Admin, session: Db) -> ControlSheetOut:
    """別のファイルNo.の内容(工程の行)をコピーして、新しく作る。"""
    return control_sheets.copy_from(session, admin, file_no, body.source_file_no)


@router.get("/{file_no}/history", response_model=list[ControlSheetOut])
def sheet_history(file_no: str, _: Admin, session: Db) -> list[ControlSheetOut]:
    """版の履歴(新しい版から。前の版の内容を見られる)。"""
    return control_sheets.history(session, file_no)
