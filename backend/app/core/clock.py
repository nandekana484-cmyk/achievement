"""時刻はすべてサーバーで記録する(開発指針 0-2)。現在時刻は必ず now() を使う(テストでは差し替えられる)。

画面の確認(Playwright)専用: GENBA_CLOCK_START(例: 2026-10-21T10:00:00+09:00)と GENBA_TEST_MODE=1 の両方が
設定されているときだけ、その時刻から時計を進める。exe(PyInstaller)では常に無効。詳細: docs/design/line-screen.md
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

logger = logging.getLogger(__name__)


def resolve_test_clock_start(env: Mapping[str, str], frozen: bool) -> datetime | None:
    """テスト用の時計の開始時刻。使ってよい条件がそろわなければ None(警告を出す)。

    本番で誤って設定されると、すべての実績の時刻がずれて記録されるため、二重に歯止めをかける。
    """
    start = env.get("GENBA_CLOCK_START")
    test_mode = env.get("GENBA_TEST_MODE") == "1"
    if not start and not test_mode:
        return None
    if frozen:
        logger.warning("exe では GENBA_CLOCK_START / GENBA_TEST_MODE を無視します(本物の時計を使います)")
        return None
    if not (start and test_mode):
        logger.warning("GENBA_CLOCK_START と GENBA_TEST_MODE=1 の片方だけが設定されています。無視して本物の時計を使います")
        return None
    base = datetime.fromisoformat(start).astimezone(JST)
    logger.warning("テスト用の時計を使います(%s から進めます)。画面の確認専用です", base)
    return base


_BASE = resolve_test_clock_start(os.environ, frozen=bool(getattr(sys, "frozen", False)))
_T0 = time.monotonic()


def now() -> datetime:
    if _BASE is not None:
        return _BASE + timedelta(seconds=time.monotonic() - _T0)
    return datetime.now(JST)
