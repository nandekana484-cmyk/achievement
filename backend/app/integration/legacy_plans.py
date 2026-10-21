"""既存アプリのDBから計画を読む入口(読み取り専用。開発指針 0-1)。中身は app/integration/legacy/。

詳細: docs/design/legacy-integration.md
"""

from app.integration.legacy.plans import read_active_plans
from app.integration.legacy.readonly import open_readonly, parse_legacy_datetime
from app.integration.legacy.source import MASTER_DB_NAME, MONTHLY_DB_NAME, find_monthly_dbs, read_legacy_source
from app.integration.legacy.takt import parse_takt_sec, read_takt_master
from app.integration.legacy.types import (
    LegacyPlan,
    LegacySourceError,
    LegacySourceRead,
    MonthlyDbRead,
    ReadResult,
    ReadWarning,
    SkippedDb,
    TaktKey,
)

__all__ = [
    "MASTER_DB_NAME",
    "MONTHLY_DB_NAME",
    "LegacyPlan",
    "LegacySourceError",
    "LegacySourceRead",
    "MonthlyDbRead",
    "ReadResult",
    "ReadWarning",
    "SkippedDb",
    "TaktKey",
    "find_monthly_dbs",
    "open_readonly",
    "parse_legacy_datetime",
    "parse_takt_sec",
    "read_active_plans",
    "read_legacy_source",
    "read_takt_master",
]
