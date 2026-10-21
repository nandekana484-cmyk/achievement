"""既存アプリのフォルダから月次DBを探し、master.db とすべての月次DBを読む。

詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from app.integration.legacy.plans import read_active_plans
from app.integration.legacy.readonly import file_mtime
from app.integration.legacy.takt import read_takt_master
from app.integration.legacy.types import LegacySourceError, LegacySourceRead, MonthlyDbRead, SkippedDb
from app.integration.legacy.workers import read_workers

MONTHLY_DB_NAME = "inventory.db"
MASTER_DB_NAME = "master.db"


def find_monthly_dbs(legacy_app_dir: Path, max_age_days: int, now: datetime) -> tuple[list[tuple[str, Path, datetime]], list[SkippedDb]]:
    """db の直下のフォルダにある inventory.db を探す。既定DB(db\\inventory.db)と古すぎるDBは読まない。"""
    db_dir = legacy_app_dir / "db"
    if not db_dir.is_dir():
        raise FileNotFoundError(f"既存アプリの db フォルダが見つかりません: {db_dir}")
    limit = now - timedelta(days=max_age_days)
    found: list[tuple[str, Path, datetime]] = []
    skipped: list[SkippedDb] = []
    for folder in sorted(p for p in db_dir.iterdir() if p.is_dir()):
        path = folder / MONTHLY_DB_NAME
        if not path.is_file():
            continue
        mtime = file_mtime(path)
        if mtime < limit:
            skipped.append(SkippedDb(folder.name, path, mtime, f"更新日時が{max_age_days}日より前"))
            continue
        found.append((folder.name, path, mtime))
    return found, skipped


def read_legacy_source(legacy_app_dir: Path, max_age_days: int, now: datetime) -> LegacySourceRead:
    """master.db と、読む対象のすべての月次DBを、DBごとに接続を開いて閉じながら読む。

    1つでも読めないDBがあれば LegacySourceError。警告の先頭にはDBのフォルダ名を付ける。
    """
    master = legacy_app_dir / "db" / MASTER_DB_NAME
    try:
        takt_master = read_takt_master(master)
        workers = read_workers(master)
    except (OSError, sqlite3.Error) as e:
        raise LegacySourceError(f"master.db を読めません({master}): {type(e).__name__}: {e}") from e

    try:
        found, skipped = find_monthly_dbs(legacy_app_dir, max_age_days, now)
    except OSError as e:
        raise LegacySourceError(f"{type(e).__name__}: {e}") from e
    if not found:
        raise LegacySourceError(f"読む月次DBがありません({legacy_app_dir / 'db'}。{max_age_days}日以内に更新された <フォルダ>\\{MONTHLY_DB_NAME} が対象)")

    dbs: list[MonthlyDbRead] = []
    for name, path, mtime in found:
        try:
            result = read_active_plans(path, takt_master)
        except (OSError, sqlite3.Error) as e:
            raise LegacySourceError(f"月次DB「{name}」を読めません({path}): {type(e).__name__}: {e}") from e
        result = replace(result, warnings=[replace(w, message=f"[{name}] {w.message}") for w in result.warnings])
        dbs.append(MonthlyDbRead(name=name, path=path, file_mtime=mtime, result=result))
    return LegacySourceRead(dbs=dbs, skipped=skipped, workers=workers)
