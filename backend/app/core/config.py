"""設定の読み込み。

PCに依存する値(ポート、パス、同期間隔)はすべて config.toml に出す。
config.toml の場所は環境変数 GENBA_CONFIG で指定する(未指定ならカレントの data/config.toml)。
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# 以前の設定項目(既存アプリのDBを1つずつ指定していた)。書かれていたら知らせる
_REMOVED_PATH_KEYS = {"legacy_database", "legacy_master_database"}


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
    # 一括取消の安全装置: 取消が cancel_guard_min 件以上 かつ 有効な計画の cancel_guard_ratio 以上なら反映しない
    cancel_guard_min: int = 10
    cancel_guard_ratio: float = 0.3
    # ファイルの更新日時がこの日数より古い月次DBは読まない
    # TODO(要確認): 読む月次DBの古さの上限
    legacy_db_max_age_days: int = 120


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    timezone: str = "Asia/Tokyo"


def _opt_path(v: str | None) -> Path | None:
    return Path(v) if v else None


def load_config(path: Path | None = None) -> AppConfig:
    path = path or Path(os.environ.get("GENBA_CONFIG", "data/config.toml"))
    if not path.exists():
        return AppConfig()

    with path.open("rb") as f:
        raw = tomllib.load(f)

    s = raw.get("server", {})
    p = raw.get("paths", {})
    y = raw.get("sync", {})
    for old in _REMOVED_PATH_KEYS & p.keys():
        logger.warning("config.toml の paths.%s は使われなくなりました。paths.legacy_app_dir を設定してください", old)
    defaults = PathsConfig()
    return AppConfig(
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
        timezone=raw.get("timezone", "Asia/Tokyo"),
    )


@lru_cache
def get_config() -> AppConfig:
    return load_config()
