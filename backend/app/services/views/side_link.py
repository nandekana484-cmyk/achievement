"""面1と面2の紐づけの、APIが返す形(ライン画面)。詳細: docs/design/actuals-export.md"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel


class SideLinkViewOut(BaseModel):
    """画面に出す紐づけの状態。2回目(side2)は入力欄、1回目(side1)は紐づいた面2の表示だけ。"""

    role: Literal["side1", "side2"]
    partner: str | None  # 明示の紐づけの相手(面2の画面では面1、面1の画面では面2)。キッティングNo.でつながっていれば、面1の画面にだけ入る
    partner_source: str | None  # field / admin / h(キッティングNo.でつながる)
    decided_by: str | None
    decided_at: dt.datetime | None
    suggested: str | None  # 欄に最初から入れておく候補(キー H でつながる面1、無ければ同じロットNo.・ファイルNo.でちょうど1つの面1)
    candidates: list[str]  # 候補(複数なら一覧から選ぶ)
