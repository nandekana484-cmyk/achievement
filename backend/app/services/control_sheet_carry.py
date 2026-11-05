"""Excel の取り込みで行を置き換えるとき、今の内容の「工程名のベトナム語」と「対応」を、同じ工程名の行に引き継ぐ(AD-28)。DBには触れない。

Excel のブックには、この2つの項目が無い(管理画面で付けたもの)。置き換えで消えないよう、次の順で今の内容の行と合わせる。
1. 同じ位置(行の番号)で、工程名が同じ行
2. 残りの行のうち、工程名がちょうど1つだけ一致する行(新しい内容の側にも、今の内容の側にも、その工程名の残りが1つだけ)
工程名が空の行(手で書く行)は合わせない。詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.control_sheets import ControlRow


@dataclass(frozen=True)
class Lost:
    """引き継げずに消える、今の内容の行(工程名が変わった・消えた行のベトナム語と対応)。row は今の内容の行の番号(1から)。"""

    row: int
    name: str
    name_vi: str | None
    link: str


@dataclass(frozen=True)
class CarryResult:
    rows: list[ControlRow]  # 新しい内容(引き継いだベトナム語と対応を入れたもの)
    carried: int  # 引き継いだ行の数(ベトナム語か対応があった行)
    lost: list[Lost]


def _has_extra(row: ControlRow) -> bool:
    return bool(row.name_vi) or row.link != "none"


def match_rows(current: list[ControlRow], new: list[ControlRow]) -> dict[int, int]:
    """新しい行の番号(0始まり) → 合わせる今の行の番号。"""
    pairs: dict[int, int] = {}
    used: set[int] = set()
    for i in range(min(len(current), len(new))):  # 1. 同じ位置で、工程名が同じ
        if new[i].name and current[i].name == new[i].name:
            pairs[i] = i
            used.add(i)
    rest_new = [i for i, r in enumerate(new) if i not in pairs and r.name]
    rest_cur = [j for j, r in enumerate(current) if j not in used and r.name]
    for i in rest_new:  # 2. 残りで、工程名がちょうど1つだけ一致する
        same_new = [k for k in rest_new if new[k].name == new[i].name]
        same_cur = [j for j in rest_cur if current[j].name == new[i].name]
        if len(same_new) == 1 and len(same_cur) == 1:
            pairs[i] = same_cur[0]
            used.add(same_cur[0])
    return pairs


def carry_over(current: list[ControlRow], new: list[ControlRow]) -> CarryResult:
    """新しい行に、合わせた今の行のベトナム語と対応を引き継ぐ。引き継げなかった今の行のうち、ベトナム語か対応があるものを lost に入れる。"""
    pairs = match_rows(current, new)
    rows = [r.model_copy(update={"name_vi": current[pairs[i]].name_vi, "link": current[pairs[i]].link}) if i in pairs else r for i, r in enumerate(new)]
    carried = sum(1 for i, j in pairs.items() if _has_extra(current[j]))
    matched = set(pairs.values())
    lost = [Lost(row=j + 1, name=r.name, name_vi=r.name_vi, link=r.link) for j, r in enumerate(current) if j not in matched and _has_extra(r)]
    return CarryResult(rows=rows, carried=carried, lost=lost)
