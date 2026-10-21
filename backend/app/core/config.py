"""設定の読み込み。

PCに依存する値(ポート、パス、同期間隔)はすべて config.toml に出す。
基準のフォルダ(GENBA_HOME): exe では環境変数 GENBA_HOME、無ければ exe の2つ上(C:\\GenbaApp\\app\\v1.0.0\\ → C:\\GenbaApp)。
開発では GENBA_HOME があればそれ、無ければ起動したフォルダ。config.toml は <基準>\\data\\config.toml(GENBA_CONFIG で変えられる)。
config.toml の相対パスは基準のフォルダから見た位置。詳細: docs/design/packaging.md
"""

from __future__ import annotations

import logging
import os
import sys
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import time
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# 以前の設定項目(既存アプリのDBを1つずつ指定していた)。書かれていたら知らせる
_REMOVED_PATH_KEYS = {"legacy_database", "legacy_master_database"}


class ConfigError(Exception):
    """config.toml を読めない(書き方の誤り)。アプリは起動しない。"""


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass(frozen=True)
class PathsConfig:
    database: Path = Path("data/genba.db")
    # 既存アプリのフォルダ。<ここ>\db\<フォルダ名>\inventory.db(月次DB)と <ここ>\db\master.db を読み取り専用で開く
    legacy_app_dir: Path | None = None
    exchange_dir: Path = Path("exchange")
    backup_dir: Path | None = None  # 共有フォルダ
    log_dir: Path = Path("logs")


@dataclass(frozen=True)
class SyncConfig:
    plan_interval_sec: int = 60
    # 一括取消の安全装置: 取消が cancel_guard_min 件以上 かつ
    # 有効な計画(計画終了が今日の 0:00 以降、または空)の cancel_guard_ratio 以上なら反映しない
    cancel_guard_min: int = 10
    cancel_guard_ratio: float = 0.3
    # ファイルの更新日時がこの日数より古い月次DBは読まない
    # TODO(要確認): 読む月次DBの古さの上限
    legacy_db_max_age_days: int = 120


@dataclass(frozen=True)
class ScheduleConfig:
    # 稼働日の始まり。稼働日 = この時刻から翌日のこの時刻まで(これより前は前日の稼働日)
    day_start: time = time(8, 15)


@dataclass(frozen=True)
class BackupConfig:
    daily_at: time = time(12, 30)  # 毎日のバックアップの時刻
    keep: int = 30  # 残す数。超えたら古い順に消す


@dataclass(frozen=True)
class AdminConfig:
    idle_minutes: int = 30  # 操作が無い時間がこれを超えたら、管理画面のログインを切る
    max_hours: int = 12  # ログインからこの時間で切る
    lockout_failures: int = 5  # 続けてこの回数間違えたら
    lockout_minutes: int = 5  # この時間ログインできない


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    timezone: str = "Asia/Tokyo"
    home: Path | None = None  # 基準のフォルダ(開発で GENBA_HOME が無ければ None = 起動したフォルダ)


def is_frozen() -> bool:
    """exe(PyInstaller)として動いているか。"""
    return bool(getattr(sys, "frozen", False))


def app_home(env: Mapping[str, str] = os.environ, frozen: bool | None = None, executable: str = sys.executable) -> Path | None:
    """基準のフォルダ。exe では GENBA_HOME か exe の2つ上。開発では GENBA_HOME か None(起動したフォルダ)。"""
    if env.get("GENBA_HOME"):
        return Path(env["GENBA_HOME"])
    if is_frozen() if frozen is None else frozen:
        return Path(executable).resolve().parents[2]
    return None


def config_path(env: Mapping[str, str] = os.environ, home: Path | None = None) -> Path:
    if env.get("GENBA_CONFIG"):
        return Path(env["GENBA_CONFIG"])
    return (home or Path()) / "data" / "config.toml"


def _at(home: Path | None, path: Path) -> Path:
    """config.toml の相対パスを、基準のフォルダから見た位置にする(基準が無ければそのまま = 起動したフォルダ)。"""
    return home / path if home is not None and not path.is_absolute() else path


def _opt_path(v: str | None) -> Path | None:
    return Path(v) if v else None


def load_config(path: Path | None = None, home: Path | None = None) -> AppConfig:
    path = path or config_path(home=home)
    if not path.exists():
        return _resolve(AppConfig(), home)

    try:
        # メモ帳や PowerShell が付ける BOM があっても読めるように utf-8-sig で読む
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"config.toml の書き方に誤りがあります({path}): {e}") from e

    s = raw.get("server", {})
    p = raw.get("paths", {})
    y = raw.get("sync", {})
    b = raw.get("backup", {})
    a = raw.get("admin", {})
    for old in _REMOVED_PATH_KEYS & p.keys():
        logger.warning("config.toml の paths.%s は使われなくなりました。paths.legacy_app_dir を設定してください", old)
    defaults = PathsConfig()
    return _resolve(AppConfig(
        server=ServerConfig(host=s.get("host", "0.0.0.0"), port=int(s.get("port", 8000))),
        paths=PathsConfig(
            database=Path(p.get("database", defaults.database)),
            legacy_app_dir=_opt_path(p.get("legacy_app_dir")),
            exchange_dir=Path(p.get("exchange_dir", defaults.exchange_dir)),
            backup_dir=_opt_path(p.get("backup_dir")),
            log_dir=Path(p.get("log_dir", defaults.log_dir)),
        ),
        sync=SyncConfig(
            plan_interval_sec=int(y.get("plan_interval_sec", 60)),
            cancel_guard_min=int(y.get("cancel_guard_min", SyncConfig.cancel_guard_min)),
            cancel_guard_ratio=float(y.get("cancel_guard_ratio", SyncConfig.cancel_guard_ratio)),
            legacy_db_max_age_days=int(y.get("legacy_db_max_age_days", SyncConfig.legacy_db_max_age_days)),
        ),
        schedule=ScheduleConfig(
            day_start=time.fromisoformat(raw.get("schedule", {}).get("day_start", ScheduleConfig.day_start.isoformat("minutes"))),
        ),
        backup=BackupConfig(
            daily_at=time.fromisoformat(b.get("daily_at", BackupConfig.daily_at.isoformat("minutes"))),
            keep=int(b.get("keep", BackupConfig.keep)),
        ),
        admin=AdminConfig(**{k: int(a.get(k, getattr(AdminConfig, k))) for k in AdminConfig.__dataclass_fields__}),
        timezone=raw.get("timezone", "Asia/Tokyo"),
    ), home)


def _resolve(cfg: AppConfig, home: Path | None) -> AppConfig:
    p = cfg.paths
    opt = lambda v: _at(home, v) if v is not None else None  # noqa: E731
    paths = PathsConfig(
        database=_at(home, p.database), legacy_app_dir=opt(p.legacy_app_dir), exchange_dir=_at(home, p.exchange_dir),
        backup_dir=opt(p.backup_dir), log_dir=_at(home, p.log_dir),
    )
    return AppConfig(server=cfg.server, paths=paths, sync=cfg.sync, schedule=cfg.schedule, backup=cfg.backup, admin=cfg.admin,
                     timezone=cfg.timezone, home=home)


@lru_cache
def get_config() -> AppConfig:
    home = app_home()
    return load_config(config_path(home=home), home)
