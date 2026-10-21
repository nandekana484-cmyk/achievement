"""回の工程の種類(開発指針 5.4)と、理由の区分(5.5)。"""

from __future__ import annotations

from enum import StrEnum


class StepType(StrEnum):
    SETUP = "setup"
    N1_CHECK = "n1_check"
    PRODUCTION = "production"
    FIRST_ARTICLE = "first_article"
    XRAY = "xray"
    CLEANUP = "cleanup"

    @property
    def label(self) -> str:
        return STEP_LABELS[self]


STEP_LABELS: dict[StepType, str] = {
    StepType.SETUP: "段取り",
    StepType.N1_CHECK: "N1チェック",
    StepType.PRODUCTION: "生産",
    StepType.FIRST_ARTICLE: "初品チェック",
    StepType.XRAY: "X線検査",
    StepType.CLEANUP: "片付け",
}


class ReasonCategory(StrEnum):
    LOSS = "loss"  # ロス
    NON_LOSS = "non_loss"  # ロス以外


class InputKind(StrEnum):
    NG_QTY = "ng_qty"
    REMARK = "remark"
