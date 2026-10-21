"""本番の起動の入口(exe もこれを動かす)。ログの出力を整え、config.toml のポートで uvicorn を起動する。

開発中でも python -m app.server で同じ形で起動できる(画面は frontend/dist を配信する)。
ログはコンソールと <log_dir>\\genba.log(日ごとに分ける)に出す。詳細: docs/design/packaging.md
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DAYS = 90  # 日ごとのログを残す日数
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(log_dir: Path) -> None:
    """コンソールと、日ごとに分けたファイルに出す。ファイルに書けなくてもアプリは止めない。"""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.TimedRotatingFileHandler(
            log_dir / "genba.log", when="midnight", backupCount=LOG_DAYS, encoding="utf-8",
        ))
    except OSError as e:
        print(f"ログのフォルダに書けません({log_dir}): {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format=_FORMAT, handlers=handlers, force=True)


def main() -> None:
    import uvicorn

    from app.core.config import get_config

    config = get_config()
    setup_logging(config.paths.log_dir)
    from app.main import app  # ログを整えてから読み込む(読み込み時の警告もファイルに残すため)

    # uvicorn のログも、上で整えた出力に流す(log_config=None)
    uvicorn.run(app, host=config.server.host, port=config.server.port, log_config=None)


if __name__ == "__main__":
    main()
