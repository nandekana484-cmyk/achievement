"""設定の読み込み。

PCに依存する値(ポート、パス、同期間隔)はすべて config.toml に出す。
config.toml の場所は環境変数 GENBA_CONFIG で指定する(未指定ならカレントの data/config.toml)。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass(frozen=True)
class PathsConfig:
    database: Path = Path("data/genba.db")
    legacy_database: Path | None = None  # 既存アプリの月次DB(計画)。読み取り専用で開く
    legacy_master_database: Path | None = None  # 既存アプリの master.db(想定タクト)
    exchange_dir: Path = Path("exchange")
    backup_dir: Path | None = None  # 共有フォルダ
    log_dir: Path = Path("logs")


@dataclass(frozen=True)
class SyncConfig:
    plan_interval_sec: int = 60
    # 一括取消の安全装置: 取消が cancel_guard_min 件以上 かつ 有効な計画の cancel_guard_ratio 以上なら反映しない
    cancel_guard_min: int = 10
    cancel_guard_ratio: float = 0.3


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
    defaults = PathsConfig()
    return AppConfig(
        server=ServerConfig(host=s.get("host", "0.0.0.0"), port=int(s.get("port", 8000))),
        paths=PathsConfig(
            database=Path(p.get("database", defaults.database)),
            legacy_database=_opt_path(p.get("legacy_database")),
            legacy_master_database=_opt_path(p.get("legacy_master_database")),
            exchange_dir=Path(p.get("exchange_dir", defaults.exchange_dir)),
            backup_dir=_opt_path(p.get("backup_dir")),
            log_dir=Path(p.get("log_dir", defaults.log_dir)),
        ),
        sync=SyncConfig(
            plan_interval_sec=int(y.get("plan_interval_sec", 60)),
            cancel_guard_min=int(y.get("cancel_guard_min", SyncConfig.cancel_guard_min)),
            cancel_guard_ratio=float(y.get("cancel_guard_ratio", SyncConfig.cancel_guard_ratio)),
        ),
        timezone=raw.get("timezone", "Asia/Tokyo"),
    )


@lru_cache
def get_config() -> AppConfig:
    return load_config()
