"""キッティングNo.ごとの生産数を、ロットに割り振る(実績の書き出し)。詳細: docs/design/actuals-export.md"""

from __future__ import annotations

from collections.abc import Sequence


def allocate(total: int, planned_qtys: Sequence[int]) -> list[int]:
    """ロットの並び順に、各ロットの計画数まで入れ、余りは最後のロットに入れる。ロットが1つなら全部をそのロットに入れる。

    合計が計画数の合計に届かなければ、後ろのロットほど少なくなる(0 もある)。
    """
    if not planned_qtys:
        return []
    result: list[int] = []
    remaining = total
    for qty in planned_qtys[:-1]:
        given = min(remaining, max(qty, 0))
        result.append(given)
        remaining -= given
    result.append(remaining)
    return result
