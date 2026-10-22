"""実績の訂正の理由・種類・どの画面からの訂正か(開発指針 5.4 の「訂正」)と、時刻の重なりの判定。

詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum


class CorrectionReason(StrEnum):
    """訂正の理由(一覧は固定)。"""

    MISTAKE = "mistake"  # 押し間違い
    FORGOT = "forgot"  # 押し忘れ
    WRONG_QTY = "wrong_qty"  # 数の入力の誤り
    OTHER = "other"  # その他(記入が必須)

    @property
    def label(self) -> str:
        return REASON_LABELS[self]


REASON_LABELS: dict[CorrectionReason, str] = {
    CorrectionReason.MISTAKE: "押し間違い",
    CorrectionReason.FORGOT: "押し忘れ",
    CorrectionReason.WRONG_QTY: "数の入力の誤り",
    CorrectionReason.OTHER: "その他",
}


class CorrectionKind(StrEnum):
    UPDATE = "update"  # 変更
    VOID = "void"  # 取り消し
    ADD = "add"  # 後からの追加


class CorrectionSource(StrEnum):
    FIELD = "field"  # 現場の画面
    ADMIN = "admin"  # 管理画面


class CompletionKind(StrEnum):
    CLEANUP = "cleanup"  # 片付けの終了で作った
    CORRECTION = "correction"  # 訂正による作り直し


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """2つの区間が重なるか(端が接するだけなら重ならない)。"""
    return a_start < b_end and b_start < a_end
