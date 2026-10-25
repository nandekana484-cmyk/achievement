"""計画のまとまり(キッティングNo.)・ライン画面用の取得・検索の、APIが返す形。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.services.kitting_plans import KittingGroup
from app.services.views import (
    CurrentOperatorOut,
    LineEventOut,
    LotOut,
    NgEntryOut,
    RunCompletionOut,
    RunEventOut,
)


class KittingPlanOut(BaseModel):
    """計画のまとまり(キッティングNo.ごと)。計画数はロットの数量の合計。"""

    kitting_no: str
    file_no: str
    line_code: str
    run_no: int  # 面
    product_name: str  # 最初のロットの基板名(ロットごとの基板名は lots)
    planned_qty: int
    planned_start: dt.datetime | None  # 日程が空のこともある
    planned_end: dt.datetime | None
    deadline: dt.datetime | None
    issue_date: dt.date
    issue_seq: int
    status: str  # active / cancelled(すべてのロットが取消のとき)
    takt_sec: float | None  # 想定タクト(1枚あたりの秒)
    source_db: str | None
    lots: list[LotOut]
    warnings: list[str]  # ロットによって値が違うとき


class NgChoiceOut(BaseModel):
    """ロットごとの、NGを入力できる面。"""

    lot_no: str
    sides: list[int]
    side1_kitting_no: str | None  # 面2の計画で面1を選べるときの、面1の計画のキッティングNo.
    note: str | None  # 選べない面があるときの理由


class BoardPlanOut(BaseModel):
    plan: KittingPlanOut
    events: list[RunEventOut]  # 工程の記録(開始の順)
    produced_qty: int  # 生産の区切りの生産数の合計(終了したもの)
    ng_entries: list[NgEntryOut]  # ロットと面ごとの最新のNG数
    ng_choices: list[NgChoiceOut]
    completed: bool
    completion: RunCompletionOut | None  # 最新の完了
    progress: float | None  # 計画の進捗率 = 生産数の合計 ÷ 計画数(計画数が0なら null)


class BoardOut(BaseModel):
    line_code: str
    date: dt.date  # 稼働日
    workday_start: dt.datetime  # 稼働日の始まり(day_start)
    workday_end: dt.datetime
    display_start: dt.datetime  # 表示範囲(稼働日の前後12時間を足した48時間)
    display_end: dt.datetime
    server_time: dt.datetime  # タブレットの時計とのずれの補正に使う
    current_operator: CurrentOperatorOut | None
    plans: list[BoardPlanOut]
    line_events: list[LineEventOut]  # 表示範囲に重なる付帯作業
    # TODO(要確認): ラインの進捗率の定義(今は 稼働日に重なる計画の生産数の合計 ÷ 計画数の合計)
    line_progress: float | None
    utilization: float | None  # 今は計算しない(稼働率の定義は要確認)


class SearchHitOut(BaseModel):
    plan: KittingPlanOut
    matched: list[str]  # 当たったところ(例: 「ロットNo. LOT-A01」「基板名 制御基板A」)


def lot_out(lot) -> LotOut:  # noqa: ANN001
    return LotOut(lot_no=lot.lot_no, product_name=lot.product_name, planned_qty=lot.planned_qty)


def kitting_plan_out(g: KittingGroup) -> KittingPlanOut:
    first = g.first
    deadlines = [lot.deadline for lot in g.lots if lot.deadline]
    return KittingPlanOut(
        kitting_no=g.kitting_no, file_no=g.file_no, line_code=g.line_code, run_no=g.run_no,
        product_name=g.product_name, planned_qty=g.planned_qty,
        planned_start=g.planned_start, planned_end=g.planned_end, deadline=min(deadlines, default=None),
        issue_date=first.issue_date, issue_seq=first.issue_seq, status=g.status, takt_sec=g.takt_sec,
        source_db=first.source_db, lots=[lot_out(lot) for lot in g.lots], warnings=g.warnings,
    )
