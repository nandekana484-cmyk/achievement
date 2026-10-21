"""計画の同期で、消えた計画を取消にするかの判定と、一括取消の安全装置。DBに触らない。

詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from app.core.config import SyncConfig
from app.db.models import Plan
from app.integration.legacy_plans import LegacyPlan, ReadWarning
from app.services.plan_diff import PlanKey
from app.services.plan_source import SourceSelection

VANISHED_LOT = "ロットがどの月次DBにも見つかりません。このロットの計画は取消にせず、そのままにします"


def ended_before(planned_end: datetime | None, today_start: datetime) -> bool:
    """計画終了が今日の 0:00 より前か。計画終了が空なら、終わっていないものとして扱う。"""
    return planned_end is not None and planned_end < today_start


def plans_to_cancel(
    missing: list[PlanKey], rows: Mapping[PlanKey, Plan], incoming: Mapping[PlanKey, LegacyPlan],
    sel: SourceSelection, today_start: datetime,
) -> tuple[list[PlanKey], list[ReadWarning]]:
    """正とするDBに無かった計画のうち、取消にするものと、この同期の警告(すべて)を返す。

    取消にするのは、ロットがどこかの月次DBにあり、かつ正とするDBにその計画が無いときだけ。
    """
    warnings = list(sel.warnings)
    # 形式エラーで読めなかった行は、既存DBに行が残っている
    unreadable = {w.key for w in sel.warnings if w.key is not None} - incoming.keys()

    removed: list[PlanKey] = []
    vanished_lots: set[str] = set()
    for key in missing:
        row = rows[key]
        if key in unreadable or ended_before(row.planned_end, today_start):
            continue
        if row.lot_no not in sel.lot_sources:
            vanished_lots.add(row.lot_no)
            continue
        removed.append(key)

    warnings += [ReadWarning(None, None, lot_no=lot, message=VANISHED_LOT) for lot in sorted(vanished_lots)]
    return removed, warnings


def count_cancellable(current: Iterable[LegacyPlan], today_start: datetime) -> int:
    """安全装置の分母: 有効な計画のうち、計画終了が今日の 0:00 以降(または空)のもの。"""
    return sum(1 for p in current if not ended_before(p.planned_end, today_start))


def cancel_guard_reason(cancel_count: int, active_count: int, cfg: SyncConfig) -> str | None:
    """一括取消の安全装置。取消が多すぎるときは、反映しない理由を返す。

    TODO(要確認): 一括取消の判定の閾値
    """
    if cancel_count >= cfg.cancel_guard_min and cancel_count >= active_count * cfg.cancel_guard_ratio:
        return (
            f"取消になる計画が多すぎるため、反映しませんでした"
            f"(取消 {cancel_count}件 / 計画終了が今日以降の有効な計画 {active_count}件。"
            f"閾値: {cfg.cancel_guard_min}件以上 かつ {cfg.cancel_guard_ratio:.0%}以上)。"
            f"既存DBの設定や切り替えを確認してください"
        )
    return None
