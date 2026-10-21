"""マスタ(ライン・作業者・設備・理由)の応答の形。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.db.models import Line


class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_code: str
    name: str
    sort_order: int
    auto_named: bool = False  # 名前が自動で付けた形(「<記号>ライン」)のままなら、画面は選んだ言語の形で出す


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # 本アプリの中の番号
    name: str
    worker_id: str | None  # 作業者ID(既存アプリの表記のまま)。同じ名前の人を区別するため、名前の横に出す
    role: str
    sort_order: int


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_code: str
    name: str
    name_vi: str | None = None  # ベトナム語の名前(空なら画面は name を出す)
    sort_order: int


class ReasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_vi: str | None = None  # ベトナム語の名前(空なら画面は name を出す)
    category: str  # loss=ロス / non_loss=ロス以外
    counts_in_utilization: bool
    requires_equipment: bool
    requires_text: bool
    usable_as_line_event: bool
    usable_as_restart: bool
    sort_order: int


class MastersOut(BaseModel):
    lines: list[LineOut]
    operators: list[OperatorOut]
    equipment: list[EquipmentOut]
    reasons: list[ReasonOut]


def line_out(line: Line) -> LineOut:
    return LineOut.model_validate(line)
