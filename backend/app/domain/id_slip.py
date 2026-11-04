"""識別票(現品票など)に印刷する値の決まり。詳細: docs/design/id-slips.md"""

from __future__ import annotations

SUF_PREFIX = "SUF-"


def display_file_no(file_no: str) -> str:
    """識別票に出すファイルNo.。数字だけなら先頭の0を外す(0722 → 722)。英字が混じる値(S010 など)はそのまま。"""
    if file_no.isdigit():
        return file_no.lstrip("0") or "0"
    return file_no


def suf_value(file_no: str) -> str:
    """下のバーコードの値。保存されている4桁のファイルNo.のまま(SUF-0722)。"""
    return SUF_PREFIX + file_no


def lot_list(lot_nos: list[str]) -> str:
    """4つ目の「Lot」の欄の文字。"""
    return ", ".join(lot_nos)
