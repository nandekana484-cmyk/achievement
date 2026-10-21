"""APIの入力(リクエストの本文)。応答の形は services/views.py と plan_views.py。

記録者は operator_id(本アプリの中の番号)か worker_id(作業者ID)のどちらかで指定できる。省略するとラインの今の担当者。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# 端末が操作ごとに作る一意のID(UUID など)
RequestId = Annotated[str, Field(min_length=1, max_length=100, description="操作ごとに一意のID。再送には同じIDを使う")]
WorkerId = Annotated[str | None, Field(default=None, max_length=64, description="作業者ID(全角・半角、大文字・小文字は区別しない)")]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Recorder(_Body):
    operator_id: int | None = None  # 省略するとラインの今の担当者
    worker_id: WorkerId = None


class ChangeOperatorIn(_Body):
    request_id: RequestId
    operator_id: int | None = None
    worker_id: WorkerId = None


class StepStartIn(_Recorder):
    request_id: RequestId
    restart_reason_id: int | None = None
    equipment_id: int | None = None  # 設備が必要な再開理由を選んだときだけ(任意。そのラインの設備)


class StepEndIn(_Recorder):
    request_id: RequestId
    produced_qty: int | None = None  # 生産の終了では必須(0以上の整数)


class NgQtyIn(_Recorder):
    request_id: RequestId
    lot_no: str = Field(max_length=100)
    side: int  # NGが出た面(1 / 2)
    ng_qty: int


class RemarkIn(_Recorder):
    request_id: RequestId
    text: str = Field(max_length=2000)


class LineEventStartIn(_Recorder):
    request_id: RequestId
    reason_id: int
    equipment_id: int | None = None
    reason_text: str | None = Field(default=None, max_length=2000)


class LineEventEndIn(_Recorder):
    request_id: RequestId
