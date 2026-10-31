"""計画のまとまり(キッティングNo.ごと)。画面と実績はこの単位で扱う。計画の取り込みはロットの単位のまま。

同じキッティングNo.の中では、ファイルNo.・ライン・面・計画開始・終了は同じはず。違うロットがあれば警告を出し、
計画開始は最も早いもの、計画終了は最も遅いもの、それ以外は最初のロット(ロットNo.の順)の値を使う。
詳細: docs/design/run-records.md
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_ACTIVE, PLAN_CANCELLED, Plan
from app.services.errors import NotFound


class LotLike(Protocol):
    """Plan(本アプリの計画の行)と LegacyPlan(既存DBから読んだ計画)に共通の項目。"""

    kitting_no: str
    lot_no: str
    file_no: str
    line_code: str
    run_no: int
    product_name: str
    planned_qty: int
    planned_start: datetime | None
    planned_end: datetime | None
    takt_sec: float | None


_SHARED = (("file_no", "ファイルNo."), ("line_code", "ライン"), ("run_no", "面"),
           ("planned_start", "計画開始"), ("planned_end", "計画終了"))


@dataclass
class KittingGroup:
    kitting_no: str
    lots: list  # ロットNo.の順。Plan または LegacyPlan
    status: str  # active / cancelled(すべてのロットが取消のときだけ cancelled)
    warnings: list[str] = field(default_factory=list)

    @property
    def first(self):  # noqa: ANN201
        return self.lots[0]

    file_no = property(lambda self: self.first.file_no)
    line_code = property(lambda self: self.first.line_code)
    run_no = property(lambda self: self.first.run_no)
    takt_sec = property(lambda self: self.first.takt_sec)
    product_name = property(lambda self: self.first.product_name)
    # 取消の理由と、出し直しで古くなったか(Plan の列。既存DBから読んだ LegacyPlan には無い)
    cancel_reason = property(lambda self: getattr(self.first, "cancel_reason", None))
    is_stale = property(lambda self: any(getattr(lot, "is_stale", False) for lot in self.lots))

    @property
    def planned_qty(self) -> int:
        return sum(lot.planned_qty for lot in self.lots)

    @property
    def planned_start(self) -> datetime | None:
        return min((lot.planned_start for lot in self.lots if lot.planned_start), default=None)

    @property
    def planned_end(self) -> datetime | None:
        return max((lot.planned_end for lot in self.lots if lot.planned_end), default=None)


def mismatch_warnings(kitting_no: str, lots: Sequence[LotLike]) -> list[str]:
    """同じキッティングNo.の中で、ロットによって違う値があれば警告の文を返す。"""
    warnings = []
    for attr, label in _SHARED:
        values = {getattr(lot, attr) for lot in lots}
        if len(values) > 1:
            warnings.append(f"キッティングNo. {kitting_no} のロットで{label}が違います(計画開始は最も早いもの、"
                            f"計画終了は最も遅いもの、それ以外は最初のロットの値を使います)")
    return warnings


def group_lots(lots: Iterable[LotLike], status_of=lambda lot: PLAN_ACTIVE) -> list[KittingGroup]:  # noqa: ANN001
    """ロットをキッティングNo.ごとにまとめる。有効なロットがあれば有効なロットだけで、なければ取消のまとまり。"""
    by_kno: dict[str, list] = {}
    for lot in lots:
        by_kno.setdefault(lot.kitting_no, []).append(lot)
    groups = []
    for kno, items in by_kno.items():
        active = sorted((x for x in items if status_of(x) != PLAN_CANCELLED), key=lambda x: x.lot_no)
        used = active or sorted(items, key=lambda x: x.lot_no)
        groups.append(KittingGroup(kno, used, PLAN_ACTIVE if active else PLAN_CANCELLED, mismatch_warnings(kno, used)))
    return groups


def _plan_status(plan: Plan) -> str:
    return plan.status


def sort_groups(groups: list[KittingGroup]) -> list[KittingGroup]:
    """計画開始の順(日程が空のものは最後)。"""
    return sorted(groups, key=lambda g: (g.planned_start is None, g.planned_start or datetime.min, g.kitting_no))


def load_group(session: Session, kitting_no: str) -> KittingGroup:
    """キッティングNo.のまとまり(取消のロットも含めて読み、有効なロットがあればそれだけでまとめる)。"""
    plans = list(session.scalars(select(Plan).where(Plan.kitting_no == kitting_no)))
    if not plans:
        raise NotFound(f"計画(キッティングNo. {kitting_no})が見つかりません")
    return group_lots(plans, _plan_status)[0]


def load_active_groups(session: Session, kitting_nos: Iterable[str]) -> list[KittingGroup]:
    """キッティングNo.ごとに、有効なロットでまとめる(計画開始の順)。"""
    knos = sorted(set(kitting_nos))
    if not knos:
        return []
    plans = session.scalars(select(Plan).where(Plan.kitting_no.in_(knos), Plan.status == PLAN_ACTIVE))
    return sort_groups(group_lots(plans))
