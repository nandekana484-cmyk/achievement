"""現場の画面での面1と面2の紐づけのAPI(2回目の作業者が、1回目のキッティングNo.を入れて紐づける)。

紐づけた人は作業者ID(operator_id / worker_id。省略するとそのラインの今の担当者)。詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.orm import Session

from app.api.schemas import RequestId, _Body, _Recorder
from app.db.session import get_session
from app.services import field_side_link
from app.services.field_side_link import SideLinkCheckOut
from app.services.views.side_link import SideLinkViewOut
from app.services.side_link_store import SOURCE_FIELD

router = APIRouter(prefix="/api", tags=["side-links"])


class SideLinkCheckIn(_Body):
    side1_kitting_no: str = Field(max_length=100, description="1回目のキッティングNo.(全角・前後の空白は整えてから探す)")


class SideLinkIn(_Recorder):
    request_id: RequestId
    side1_kitting_no: str = Field(max_length=100)
    confirm_lot_mismatch: bool = Field(default=False, description="合わないロットの警告を確認した")


class SideUnlinkIn(_Recorder):
    request_id: RequestId


@router.post("/runs/{kitting_no}/side-link/check", response_model=SideLinkCheckOut)
def check_side_link(kitting_no: str, body: SideLinkCheckIn, session: Session = Depends(get_session)) -> SideLinkCheckOut:
    """紐づける前の確かめ(断る理由、合わないロットの警告、書き出し済みか)。何も記録しない。"""
    return field_side_link.check(session, kitting_no, body.side1_kitting_no)


@router.post("/runs/{kitting_no}/side-link", response_model=SideLinkViewOut)
def link_side(kitting_no: str, body: SideLinkIn, session: Session = Depends(get_session)) -> SideLinkViewOut:
    """面2に面1を紐づける(直しも同じ。最後に保存したものが有効)。断る理由があれば 409。"""
    actor = field_side_link.resolve_actor(session, kitting_no, body.operator_id, body.worker_id)
    return field_side_link.link(session, actor, SOURCE_FIELD, kitting_no, body.side1_kitting_no, body.confirm_lot_mismatch, body.request_id)


@router.post("/runs/{kitting_no}/side-link/unlink", response_model=SideLinkViewOut)
def unlink_side(kitting_no: str, body: SideUnlinkIn, session: Session = Depends(get_session)) -> SideLinkViewOut:
    """面2の明示の紐づけを外す(キッティングNo.でつながっているものは外せない)。"""
    actor = field_side_link.resolve_actor(session, kitting_no, body.operator_id, body.worker_id)
    return field_side_link.unlink(session, actor, SOURCE_FIELD, kitting_no, body.request_id)  # type: ignore[return-value]
