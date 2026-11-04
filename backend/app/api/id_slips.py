"""識別票の印刷用のAPI(現場の画面。読み取りだけ)。認証は現場の画面と同じ(IP制限)。詳細: docs/design/id-slips.md"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.id_slips import IdSlipOut, build_id_slips

router = APIRouter(prefix="/api/id-slips", tags=["id-slips"])


@router.get("/{kitting_no}", response_model=IdSlipOut)
def get_id_slips(kitting_no: str, session: Session = Depends(get_session)) -> IdSlipOut:
    """キッティングNo.の識別票に印刷する値(ファイルNo.、製品名、全ロット、C)。"""
    return build_id_slips(session, kitting_no)
