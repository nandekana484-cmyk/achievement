"""APIの入力(リクエストの本文)。応答の形は services/views.py。"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# 端末が操作ごとに作る一意のID(UUID など)
RequestId = Annotated[str, Field(min_length=1, max_length=100, description="操作ごとに一意のID。再送には同じIDを使う")]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChangeOperatorIn(_Body):
    request_id: RequestId
    operator_id: int


class StepStartIn(_Body):
    request_id: RequestId
    restart_reason_id: int | None = None
    operator_id: int | None = None  # 省略するとラインの今の担当者


class StepEndIn(_Body):
    request_id: RequestId
    produced_qty: int | None = None  # 生産の終了では必須(0以上の整数)
    operator_id: int | None = None


class NgQtyIn(_Body):
    request_id: RequestId
    ng_qty: int
    operator_id: int | None = None


class RemarkIn(_Body):
    request_id: RequestId
    text: str = Field(max_length=2000)
    operator_id: int | None = None


class LineEventStartIn(_Body):
    request_id: RequestId
    reason_id: int
    equipment_id: int | None = None
    reason_text: str | None = Field(default=None, max_length=2000)
    operator_id: int | None = None


class LineEventEndIn(_Body):
    request_id: RequestId
    operator_id: int | None = None
