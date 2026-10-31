"""管理画面の「丁取り」のAPI: 丁取りが引けない計画の一覧(見るだけ)。管理者のログインが要る。詳細: docs/design/metrics.md"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.db.models import Operator
from app.db.session import get_session
from app.services import teitori_unresolved

router = APIRouter(prefix="/api/admin/teitori", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]


@router.get("/unresolved", response_model=teitori_unresolved.UnresolvedOut)
def unresolved(_: Admin, session: Db) -> teitori_unresolved.UnresolvedOut:
    """丁取りが引けない有効な計画(キッティングNo.、ファイルNo.、ライン、status)。"""
    return teitori_unresolved.unresolved_plans(session)
