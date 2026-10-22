"""APIの入力(リクエストの本文)。応答の形は services/views/ と plan_views.py。

記録者は operator_id(本アプリの中の番号)か worker_id(作業者ID)のどちらかで指定できる。省略するとラインの今の担当者。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.steps import StepType

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


class _CorrectionIn(_Recorder):
    """訂正の共通。理由は mistake(押し間違い)/ forgot(押し忘れ)/ wrong_qty(数の入力の誤り)/ other(その他。記入が必須)。"""

    request_id: RequestId
    reason: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class RunEventCorrectIn(_CorrectionIn):
    """工程の記録の訂正。直す項目だけ送る(時刻はタイムゾーン付き)。"""

    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    produced_qty: int | None = None  # 生産の区切りの生産数


class RunEventAddIn(_CorrectionIn):
    """押し忘れた工程の後からの追加。"""

    step_type: StepType
    start_at: AwareDatetime
    end_at: AwareDatetime
    produced_qty: int | None = None  # 生産では必須


class LineEventCorrectIn(_CorrectionIn):
    """付帯作業の訂正。直す項目だけ送る。"""

    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    reason_id: int | None = None
    equipment_id: int | None = None  # 設備をなくすときは null を送る
    reason_text: str | None = Field(default=None, max_length=2000)


class VoidIn(_CorrectionIn):
    """記録の取り消し。"""


CORRECTION_META = {"request_id", "reason", "note", "operator_id", "worker_id"}
