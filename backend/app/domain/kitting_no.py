"""キッティングNo.の解析。

形式: ファイルNo.-回-生産ライン-発行年月日-その日の発行順
例:   0722-2-S-251014-01

TODO(要確認): キッティングNo.の各部分の桁数(現在の正規表現は例から推定したもの)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_PATTERN = re.compile(
    r"^(?P<file_no>[^-]+)-(?P<run_no>[12])-(?P<line_code>[^-]+)-(?P<issue_date>\d{6})-(?P<issue_seq>\d+)$"
)


class KittingNoError(ValueError):
    """形式に合わないキッティングNo.。取り込まずに警告を出す。"""


@dataclass(frozen=True)
class KittingNo:
    raw: str
    file_no: str
    run_no: int  # 1=1回目(表)、2=2回目(裏)
    line_code: str
    issue_date: date  # 発行年月日(生産日ではない)
    issue_seq: int

    @property
    def issue_order_key(self) -> tuple[date, int]:
        """組の候補が重なったとき、発行日と発行順が早いものを先にするためのキー。"""
        return (self.issue_date, self.issue_seq)


def parse_kitting_no(value: str) -> KittingNo:
    raw = value.strip()
    m = _PATTERN.match(raw)
    if m is None:
        raise KittingNoError(f"キッティングNo.の形式に合いません: {value!r}")

    d = m.group("issue_date")
    try:
        issue_date = date(2000 + int(d[0:2]), int(d[2:4]), int(d[4:6]))
    except ValueError as e:
        raise KittingNoError(f"発行年月日が日付として不正です: {value!r}") from e

    return KittingNo(
        raw=raw,
        file_no=m.group("file_no"),
        run_no=int(m.group("run_no")),
        line_code=m.group("line_code"),
        issue_date=issue_date,
        issue_seq=int(m.group("issue_seq")),
    )
