"""管理画面のマスタのAPI(設備・理由・ライン・作業者)。すべて管理者のログインが要る。変更は audit_log に残す。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.admin import current_admin, require_header_for_writes
from app.core.config import get_config
from app.db.models import Operator
from app.db.session import get_session
from app.services import admin_masters as svc
from app.services.admin_masters import EquipmentAdminOut, LineAdminOut, OperatorAdminOut, ReasonAdminOut

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_header_for_writes)])

Admin = Annotated[Operator, Depends(current_admin)]
Db = Annotated[Session, Depends(get_session)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
NameVi = Annotated[str | None, Field(default=None, max_length=100)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def changes(self) -> dict:
        """送られてきた項目だけ(送られていない項目は変えない)。"""
        return {k: getattr(self, k) for k in self.model_fields_set}


class EquipmentIn(_Body):
    line_code: str = Field(min_length=1, max_length=20)
    name: Name
    name_vi: NameVi = None
    sort_order: int | None = None


class EquipmentPatch(_Body):
    name: Name | None = None
    name_vi: NameVi = None
    sort_order: int | None = None
    active: bool | None = None


class ReasonIn(_Body):
    name: Name
    name_vi: NameVi = None
    category: str = "loss"
    requires_equipment: bool = False
    requires_text: bool = False
    usable_as_line_event: bool = False
    usable_as_restart: bool = False
    counts_in_utilization: bool = False
    sort_order: int | None = None


class ReasonPatch(_Body):
    name: Name | None = None
    name_vi: NameVi = None
    category: str | None = None
    requires_equipment: bool | None = None
    requires_text: bool | None = None
    usable_as_line_event: bool | None = None
    usable_as_restart: bool | None = None
    counts_in_utilization: bool | None = None
    sort_order: int | None = None
    active: bool | None = None


class LinePatch(_Body):
    name: Name | None = None
    sort_order: int | None = None
    active: bool | None = None


class OperatorIn(_Body):
    name: Name
    worker_id: str | None = Field(default=None, max_length=32)


@router.get("/equipment", response_model=list[EquipmentAdminOut])
def list_equipment(_: Admin, session: Db) -> list:
    """設備の一覧(無効なものも含む)。"""
    return svc.list_equipment(session)


@router.post("/equipment", response_model=EquipmentAdminOut)
def add_equipment(body: EquipmentIn, admin: Admin, session: Db) -> object:
    """設備を追加する。"""
    return svc.add_equipment(session, admin.id, body.line_code, body.model_dump(exclude={"line_code"}))


@router.patch("/equipment/{equipment_id}", response_model=EquipmentAdminOut)
def update_equipment(equipment_id: int, body: EquipmentPatch, admin: Admin, session: Db) -> object:
    """設備の名前(日本語・ベトナム語)・並び順を変える。active=false で無効にする(消さない)。"""
    return svc.update_equipment(session, admin.id, equipment_id, body.changes())


@router.get("/reasons", response_model=list[ReasonAdminOut])
def list_reasons(_: Admin, session: Db) -> list:
    """理由の一覧(無効なものも含む)。"""
    return svc.list_reasons(session)


@router.post("/reasons", response_model=ReasonAdminOut)
def add_reason(body: ReasonIn, admin: Admin, session: Db) -> object:
    """理由を追加する。"""
    return svc.add_reason(session, admin.id, body.model_dump())


@router.patch("/reasons/{reason_id}", response_model=ReasonAdminOut)
def update_reason(reason_id: int, body: ReasonPatch, admin: Admin, session: Db) -> object:
    """理由の名前・区分・入力の決まり・使い道・稼働率に含めるか・並び順を変える。active=false で無効にする。"""
    return svc.update_reason(session, admin.id, reason_id, body.changes())


@router.get("/lines", response_model=list[LineAdminOut])
def list_lines(_: Admin, session: Db) -> list:
    """ラインの一覧(無効なものも含む)。"""
    return svc.list_lines(session)


@router.patch("/lines/{line_code}", response_model=LineAdminOut)
def update_line(line_code: str, body: LinePatch, admin: Admin, session: Db) -> object:
    """ラインの名前・並び順を変える。active=false で無効にする。"""
    return svc.update_line(session, admin.id, line_code, body.changes())


@router.get("/operators", response_model=list[OperatorAdminOut])
def list_operators(_: Admin, session: Db) -> list[OperatorAdminOut]:
    """作業者の一覧(見るだけ。既存アプリから読み込む)。"""
    return svc.list_operators(session)


@router.post("/operators", response_model=OperatorAdminOut)
def add_operator(body: OperatorIn, admin: Admin, session: Db) -> OperatorAdminOut:
    """開発用の作業者を足す(legacy_app_dir が設定されていない環境だけ)。"""
    op = svc.add_local_operator(session, admin.id, body.name, body.worker_id, get_config().paths.legacy_app_dir is not None)
    return OperatorAdminOut(id=op.id, name=op.name, worker_id=op.worker_id, role=op.role, active=op.active,
                            source=op.source, has_password=False)
