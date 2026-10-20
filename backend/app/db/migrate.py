"""起動時にDBの構造を最新に更新する(Alembic)。

マイグレーションの場所は __file__ 基準で決める。カレントフォルダや alembic.ini の場所には依存しないので、
PyInstaller で exe にしても、migrations フォルダを app/db/ の下に同梱すれば動く。
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    """本アプリのDBを最新の構造にする。何度呼んでもよい。

    TODO(バックアップ実装後): 更新の前にバックアップを取る(開発指針 10)
    """
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
