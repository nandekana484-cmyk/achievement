"""管理画面の「引き継ぎの確認」のAPI: 実績のある取り消された・古い計画の一覧と、移す先の確定。管理者のログインが要る。

詳細: docs/design/legacy-integration.md(実績の引き継ぎ)
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.db.models import Operator
from app.db.session import get_session
from app.services import handover
from app.services.handover import HandoverListOut, HandoverResultOut

router = APIRouter(prefix="/api/admin/handovers", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


class ConfirmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_kitting_no: str = Field(max_length=100, description="実績のある、取り消された・古い計画")
    new_kitting_no: str = Field(max_length=100, description="実績を移す先(候補の中から選ぶ)")


@router.get("", response_model=HandoverListOut)
def list_handovers(_: Admin, session: Db) -> HandoverListOut:
    """引き継ぎの確認の一覧(移す先の候補つき)と、確定した履歴(新しい順に50件)。"""
    return handover.handover_list(session)


@router.post("/confirm", response_model=HandoverResultOut)
def confirm(admin: Admin, session: Db, body: ConfirmIn) -> HandoverResultOut:
    """実績を新しいキッティングNo.へ移す。移す先に実績がある・候補にないときは 409。自動では移さない。"""
    return handover.confirm_handover(session, admin, body.old_kitting_no, body.new_kitting_no)
