"""本アプリのDBのバックアップ(開発指針 9)。SQLite のバックアップ機能で、config.toml の paths.backup_dir に保存する。

- 起動したとき(マイグレーションの前)と、毎日決まった時刻(backup.daily_at)に取る。起動中のファイルのコピーはしない
- ファイル名に日時を入れ、backup.keep を超えたら古い順に消す。消すのは本アプリが作った名前のファイルだけ
- 保存先が未設定・書き込めないときは、アプリを止めずに警告をログに出す
詳細: docs/design/packaging.md
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import sqlite3
from datetime import datetime, time, timedelta
from pathlib import Path

from app.core import clock
from app.core.config import BackupConfig

logger = logging.getLogger(__name__)

# genba_20261021_123000_daily.db(本アプリが作ったバックアップだけが、この名前になる)
_NAME = re.compile(r"^genba_\d{8}_\d{6}(?:-\d+)?_[a-z]+\.db$")


def backup_name(now: datetime, reason: str) -> str:
    return f"genba_{now.strftime('%Y%m%d_%H%M%S')}_{reason}.db"


def make_backup(db_path: Path, backup_dir: Path | None, keep: int, reason: str) -> Path | None:
    """DBを backup_dir に保存し、古いものを消す。保存したファイルを返す。保存できなければ警告を出して None。"""
    if backup_dir is None:
        logger.warning("paths.backup_dir が設定されていないため、DBのバックアップを取りません")
        return None
    if not db_path.exists():
        logger.info("DBがまだ無いため、バックアップは取りません(%s)", db_path)
        return None
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = _unused(backup_dir / backup_name(clock.now(), reason))
        tmp = target.with_suffix(".tmp")  # 書き終える前のファイルを、バックアップと取り違えないように
        with contextlib.closing(sqlite3.connect(db_path, timeout=10)) as src, contextlib.closing(sqlite3.connect(tmp)) as dst:
            src.backup(dst)
        tmp.replace(target)
    except (OSError, sqlite3.Error) as e:
        logger.warning("DBのバックアップを取れませんでした(保存先 %s): %s: %s", backup_dir, type(e).__name__, e)
        return None
    logger.info("DBのバックアップを取りました: %s", target)
    prune_backups(backup_dir, keep)
    return target


def _unused(path: Path) -> Path:
    """同じ秒に2回取ったときは、名前に番号を付ける。"""
    n = 2
    candidate = path
    while candidate.exists():
        stem = path.name.split("_")
        candidate = path.with_name(f"{'_'.join(stem[:3])}-{n}_{stem[3]}")
        n += 1
    return candidate


def prune_backups(backup_dir: Path, keep: int) -> list[Path]:
    """本アプリが作ったバックアップのうち、新しいものから keep 個を残して消す。消したファイルを返す。"""
    ours = sorted(p for p in backup_dir.iterdir() if p.is_file() and _NAME.match(p.name))
    removed: list[Path] = []
    for old in ours[: max(0, len(ours) - keep)]:
        try:
            old.unlink()
            removed.append(old)
        except OSError as e:
            logger.warning("古いバックアップを消せませんでした: %s: %s", old, e)
    return removed


def seconds_until(now: datetime, at: time) -> float:
    """now から、次の at(今日の at が過ぎていれば明日の at)までの秒数。"""
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


class DailyBackup:
    """毎日 daily_at にバックアップを取る asyncio のタスク(バックアップそのものは別スレッドで行う)。"""

    def __init__(self, db_path: Path, backup_dir: Path | None, cfg: BackupConfig) -> None:
        self._db_path, self._backup_dir, self._cfg = db_path, backup_dir, cfg
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="daily-backup")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(seconds_until(clock.now(), self._cfg.daily_at))
            try:
                await asyncio.to_thread(make_backup, self._db_path, self._backup_dir, self._cfg.keep, "daily")
            except Exception:  # noqa: BLE001  次の日も取る
                logger.exception("毎日のバックアップで想定外のエラーが起きました")
