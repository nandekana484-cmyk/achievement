"""起動時にDBの構造を最新に更新する(Alembic)。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"  # exe にしても動くよう __file__ 基準


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    """本アプリのDBを最新の構造にする。何度呼んでもよい。

    更新の前のバックアップは、アプリの起動時(main.py の lifespan)にこの前で取る。
    """
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
