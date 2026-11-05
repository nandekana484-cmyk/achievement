"""計画のまとまり(キッティングNo.)・ライン画面用の取得・検索の、APIが返す形。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.services.kitting_plans import KittingGroup
from app.services.plan_closures import ClosureOut
from app.services.views.side_link import SideLinkViewOut
from app.services.views.metrics import EfficiencyOut
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
    cancel_reason: str | None  # 取消の理由: vanished(読めなくなった)/ reissued(出し直し)/ carried_over(引き継ぎ済み)
    is_stale: bool  # 出し直しで古くなった計画(実績があるので取り消していない。管理画面の「引き継ぎの確認」の対象)
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
    side_link: SideLinkViewOut | None  # 面1と面2の紐づけ(面2は入力欄、面1は紐づいた面2の表示だけ)
    closed: ClosureOut | None  # 計画終了している(手動。完了とは別)ときの、理由・記入・押した人
    in_progress: bool  # 生産中(最初の工程を始め、片付けが終わっていない)
    progress: float | None  # 進捗率 = 工程の記録の時間の合計 ÷ 計画の時間。生産中でない・計画の時間が無いときは null


class StalePlanOut(BaseModel):
    kitting_no: str
    lot_nos: list[str]
    planned_start: dt.datetime
    planned_end: dt.datetime


class BoardOut(BaseModel):
    line_code: str
    date: dt.date  # 表示している稼働日
    today: dt.date  # 今の稼働日(date と違えば「表示のみ」。範囲を広げる・警告は今日だけ)
    workday_start: dt.datetime  # 稼働日の始まり(day_start)
    workday_end: dt.datetime
    display_start: dt.datetime  # 表示範囲(稼働日の前後12時間。片付け前の計画があれば始まりを広げる)
    display_end: dt.datetime
    stale_plans_total: int  # 上のうち、警告の対象の全体の件数(stale_plans は古い順の最初の5件だけ)
    stale_plans: list[StalePlanOut]  # 広げても範囲に入らない、遅れた未着手の計画(画面で警告する。検索で選んで計画終了か作業開始)
    stale_kitting_nos: list[str]  # 広げても表示範囲に入りきらない、片付けが終わっていない計画(画面で警告する)
    server_time: dt.datetime  # タブレットの時計とのずれの補正に使う
    current_operator: CurrentOperatorOut | None
    plans: list[BoardPlanOut]
    line_events: list[LineEventOut]  # 表示範囲に重なる付帯作業
    efficiency: EfficiencyOut  # この稼働日の効率(詳細: docs/design/metrics.md)


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
        issue_date=first.issue_date, issue_seq=first.issue_seq, status=g.status, cancel_reason=g.cancel_reason, is_stale=g.is_stale, takt_sec=g.takt_sec,
        source_db=first.source_db, lots=[lot_out(lot) for lot in g.lots], warnings=g.warnings,
    )
