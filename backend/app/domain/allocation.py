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


def balance(total: int, planned_qtys: Sequence[int], index: int) -> list[int] | None:
    """index 番目のロットで差を調整する: ほかのロットは計画数どおり、そのロットは「合計 - ほかの合計」。0 未満になるときは None。"""
    others = sum(max(q, 0) for i, q in enumerate(planned_qtys) if i != index)
    rest = total - others
    if rest < 0:
        return None
    return [rest if i == index else max(q, 0) for i, q in enumerate(planned_qtys)]
