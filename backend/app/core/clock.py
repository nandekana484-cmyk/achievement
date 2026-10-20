"""時刻はすべてサーバーで記録する(開発指針 0-2)。

アプリ内で現在時刻が必要なときは、必ず now() を使う。テストでは差し替えられる。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now() -> datetime:
    return datetime.now(JST)
