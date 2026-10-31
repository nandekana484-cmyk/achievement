"""効率と進捗率の、APIが返す形。計算は services/metrics.py。"""

from __future__ import annotations

from pydantic import BaseModel


class ExcludedPlanOut(BaseModel):
    kitting_no: str
    reason: str  # 丁取りの status(ok 以外)、no_row(丁取りの行が無い)、no_takt(目標タクトが無い)


class ReasonCountOut(BaseModel):
    reason: str
    count: int


class EfficiencyOut(BaseModel):
    """その稼働日の効率。efficiency は割合(0.8 = 80%)。計算に入れた計画が無い・実所要時間が0なら null。"""

    efficiency: float | None
    standard_seconds: float  # Σ(目標タクト × 良品台数 ÷ 丁取り数)
    actual_seconds: float  # Σ(実所要時間)
    included: int  # 計算に入れた計画(キッティングNo.)の数
    excluded: int  # 目標タクトか丁取り数が無くて外した計画の数
    reasons: list[ReasonCountOut]  # 外した理由ごとの件数
    excluded_plans: list[ExcludedPlanOut]
    warnings: list[str]


class ProgressOut(BaseModel):
    in_progress: bool  # 生産中 = 最初の工程を始め、片付けが終わっていない
    progress: float | None  # 割合(1.2 = 120%。100%を超えてもそのまま)。生産中でない・計画の時間が無い・0以下なら null
