"""本番の起動の入口(exe もこれを動かす)。ログの出力を整え、config.toml のポートで uvicorn を起動する。

開発中でも python -m app.server で同じ形で起動できる(画面は frontend/dist を配信する)。
ログは <log_dir>\\genba.log(日ごとに分ける)と、コンソールがあればコンソールに出す。
ウィンドウを出さない exe でも起動の失敗が分かるよう、設定を読む前から <基準>\\logs にログを出す。詳細: docs/design/packaging.md
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DAYS = 90  # 日ごとのログを残す日数
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

logger = logging.getLogger(__name__)


def setup_logging(log_dir: Path) -> None:
    """日ごとに分けたファイルと、コンソールがあればコンソールに出す。ファイルに書けなくてもアプリは止めない。"""
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:  # ウィンドウを出さない exe では stderr が無い
        handlers.append(logging.StreamHandler(sys.stderr))
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.TimedRotatingFileHandler(
            log_dir / "genba.log", when="midnight", backupCount=LOG_DAYS, encoding="utf-8",
        ))
    except OSError as e:
        print(f"ログのフォルダに書けません({log_dir}): {e}", file=sys.stderr)
    logging.basicConfig(level=logging.INFO, format=_FORMAT, handlers=handlers or [logging.NullHandler()], force=True)


def default_log_dir() -> Path:
    """設定を読む前のログの場所(<基準>\\logs。config.toml の log_dir の既定と同じ)。"""
    from app.core.config import app_home

    return (app_home() or Path()) / "logs"


def main() -> int:
    """起動し、止まるまで動かす。起動できなければ理由をログに出して 1 を返す。"""
    setup_logging(default_log_dir())  # 設定の誤りで止まるときも、理由をファイルに残すため
    try:
        import uvicorn

        from app import __version__
        from app.core.config import get_config

        config = get_config()
        if config.paths.log_dir.resolve() != default_log_dir().resolve():
            setup_logging(config.paths.log_dir)
        from app.main import app  # ログを整えてから読み込む(読み込み時の警告もファイルに残すため)

        logger.info("起動します(版 %s、%s:%s)", __version__, config.server.host, config.server.port)
        # uvicorn のログも、上で整えた出力に流す(log_config=None)。ポートの使用中などは uvicorn がログに出して終了する
        uvicorn.run(app, host=config.server.host, port=config.server.port, log_config=None)
    except SystemExit as e:
        if e.code not in (0, None):
            logger.error("起動できずに終了しました(終了コード %s)。理由は上のログを見てください", e.code)
        return e.code if isinstance(e.code, int) else 1
    except Exception:
        logger.exception("起動できませんでした")
        return 1
    logger.info("停止しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
