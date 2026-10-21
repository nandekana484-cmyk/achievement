"""時刻はすべてサーバーで記録する(開発指針 0-2)。現在時刻は必ず now() を使う(テストでは差し替えられる)。

画面の確認(Playwright)専用: 環境変数 GENBA_CLOCK_START(例: 2026-10-21T10:00:00+09:00)を指定すると、
その時刻から時計を進める(撮る時刻によって画面が変わらないように)。本番では指定しない。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

_START = os.environ.get("GENBA_CLOCK_START")
_BASE = datetime.fromisoformat(_START).astimezone(JST) if _START else None
_T0 = time.monotonic()
if _BASE is not None:
    logging.getLogger(__name__).warning("GENBA_CLOCK_START が指定されています。時計を %s から進めます(画面の確認専用)", _BASE)


def now() -> datetime:
    if _BASE is not None:
        return _BASE + timedelta(seconds=time.monotonic() - _T0)
    return datetime.now(JST)
