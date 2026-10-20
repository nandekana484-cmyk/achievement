"""Alembic の実行環境。

- アプリから呼ぶとき(app/db/migrate.py): 渡された接続をそのまま使う
- コマンドから呼ぶとき(alembic.ini): config.toml の paths.database に接続する
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.db import models  # noqa: F401  テーブルを Base.metadata に登録する
from app.db.session import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:  # noqa: ANN001
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite は ALTER TABLE が弱いので、列の変更はテーブルの作り直しで行う
    )
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)

    from app.core.config import get_config
    from app.db.session import make_engine

    engine = make_engine(get_config().paths.database)
    with engine.begin() as conn:
        _run(conn)
    engine.dispose()
