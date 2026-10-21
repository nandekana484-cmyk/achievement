"""既存アプリのDBから読んだ結果の型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TaktKey = tuple[str, str, int]  # (正規化したファイルNo., 正規化した実装ライン, 面)


@dataclass(frozen=True)
class LegacyPlan:
    """既存アプリの有効な計画1行を、本アプリで扱う形に直したもの。"""

    kitting_no: str
    lot_no: str
    file_no: str  # 正規化した値
    line_code: str  # 正規化した値
    product_name: str
    run_no: int  # 面。1=1回目、2=2回目
    planned_qty: int
    cumulative_qty: int | None
    order_qty: int | None
    planned_start: datetime | None
    planned_end: datetime | None
    deadline: datetime | None
    delete_flag: bool  # 保存するだけ。取消の判定には使わない
    status: str | None
    legacy_plan_item_id: int
    legacy_version: int
    # TODO(要確認): 想定タクトの単位(今は「1枚あたりの秒」と仮定)
    takt_sec: float | None = None

    @property
    def key(self) -> tuple[str, str]:
        """計画の識別キー(キッティングNo.+ロットNo.)。"""
        return (self.kitting_no, self.lot_no)

    def content(self) -> tuple:
        """変化の判定に使う内容。版・行番号・削除フラグは含めない。"""
        return (
            self.file_no, self.line_code, self.product_name, self.run_no,
            self.planned_qty, self.cumulative_qty, self.order_qty,
            self.planned_start, self.planned_end, self.deadline,
            self.status, self.takt_sec,
        )


@dataclass(frozen=True)
class ReadWarning:
    legacy_plan_item_id: int | None
    kitting_no: str | None
    message: str
    lot_no: str | None = None

    @property
    def key(self) -> tuple[str, str] | None:
        """警告の行の計画のキー。キッティングNo.が空なら計画と結びつけられないので None。"""
        if not self.kitting_no or self.lot_no is None:
            return None
        return (self.kitting_no, self.lot_no)


@dataclass(frozen=True)
class ReadResult:
    plans: list[LegacyPlan]
    warnings: list[ReadWarning]
    # ロットごとの最終書き込み時刻。時刻が読めないロットは None
    lot_last_written: dict[str, datetime | None] = field(default_factory=dict)


@dataclass(frozen=True)
class MonthlyDbRead:
    """月次DB 1つ分の読み取り結果。"""

    name: str  # DBのフォルダ名
    path: Path
    file_mtime: datetime
    result: ReadResult


@dataclass(frozen=True)
class SkippedDb:
    name: str
    path: Path
    file_mtime: datetime
    reason: str


@dataclass(frozen=True)
class LegacySourceRead:
    """既存アプリのすべての月次DBの読み取り結果。"""

    dbs: list[MonthlyDbRead]
    skipped: list[SkippedDb]


class LegacySourceError(Exception):
    """既存アプリのDBを読めなかった(1つでも読めなければ、同期は何も反映しない)。"""
