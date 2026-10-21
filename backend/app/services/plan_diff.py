"""計画の差分の判定(開発指針 6.1)。DBに触らない純粋な処理。

既存アプリは内容が同じでも版を上げるので、version ではなく内容(LegacyPlan.content)で比べる。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.integration.legacy_plans import LegacyPlan

PlanKey = tuple[str, str]  # (キッティングNo., ロットNo.)


@dataclass(frozen=True)
class CarryoverCandidate:
    """実績のある計画が消え、ロットNo.・ファイルNo.・回が同じ新しい計画が現れたもの。"""

    old_key: PlanKey
    new_keys: tuple[PlanKey, ...]

    @property
    def is_unique(self) -> bool:
        return len(self.new_keys) == 1


@dataclass
class PlanDiff:
    added: list[LegacyPlan] = field(default_factory=list)
    changed: list[LegacyPlan] = field(default_factory=list)
    unchanged: list[PlanKey] = field(default_factory=list)
    removed_without_actuals: list[PlanKey] = field(default_factory=list)
    removed_with_actuals: list[PlanKey] = field(default_factory=list)  # 取消(実績あり)
    carryovers: list[CarryoverCandidate] = field(default_factory=list)


def diff_plans(
    current: Mapping[PlanKey, LegacyPlan],
    incoming: Iterable[LegacyPlan],
    keys_with_actuals: set[PlanKey],
) -> PlanDiff:
    """current: 本アプリが今持っている計画、incoming: 既存DBから読んだ有効な計画。

    削除フラグ(delete_flag)は考慮しない(業務上の意味が分からず、実データでもすべて0のため)。
    removed_* は「incoming に無い」というだけで、取消にするかどうかは呼び出し側(plan_sync)が決める。
    """
    live = {p.key: p for p in incoming}
    d = PlanDiff()

    for key, plan in live.items():
        old = current.get(key)
        if old is None:
            d.added.append(plan)
        elif old.content() != plan.content():
            d.changed.append(plan)
        else:
            d.unchanged.append(key)

    for key in current:
        if key in live:
            continue
        if key in keys_with_actuals:
            d.removed_with_actuals.append(key)
        else:
            d.removed_without_actuals.append(key)

    # 番号の振り直しの引き継ぎ候補: 消えた実績あり計画 × 同じ回で新しく現れた計画
    for old_key in d.removed_with_actuals:
        old = current[old_key]
        matches = tuple(
            p.key for p in d.added
            if p.lot_no == old.lot_no and p.file_no == old.file_no and p.run_no == old.run_no
        )
        if matches:
            d.carryovers.append(CarryoverCandidate(old_key, matches))

    return d
