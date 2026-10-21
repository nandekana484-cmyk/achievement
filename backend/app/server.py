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


EXIT_ALREADY_RUNNING = 2  # 同じDBで、ほかのプロセスが動いている
EXIT_PORT_IN_USE = 4  # 使うポートが、ほかのプログラムに使われている(uvicorn の起動の失敗は 3)


def main() -> int:
    """起動し、止まるまで動かす。起動できなければ理由をログに出して 0 以外を返す。"""
    setup_logging(default_log_dir())  # 設定の誤りで止まるときも、理由をファイルに残すため
    lock = None
    try:
        import uvicorn

        from app import __version__
        from app.core.config import get_config
        from app.core.single_instance import AlreadyRunning, InstanceLock, port_available

        config = get_config()
        if config.paths.log_dir.resolve() != default_log_dir().resolve():
            setup_logging(config.paths.log_dir)

        # 起動処理(バックアップとマイグレーション)の前に確かめる。古い版を止め忘れたまま新しい版を起動しても、
        # 動いている古い版の下でDBの形を変えないように
        lock = InstanceLock(config.paths.database.parent / "genba.lock")
        try:
            lock.acquire()
        except AlreadyRunning as e:
            logger.error("起動しません: %s。同じフォルダの GenbaApp を止めてから起動してください", e)
            return EXIT_ALREADY_RUNNING
        if not port_available(config.server.host, config.server.port):
            logger.error("起動しません: ポート %s はほかのプログラムが使っています(config.toml の server.port)", config.server.port)
            return EXIT_PORT_IN_USE

        from app.main import app  # ログを整えてから読み込む(読み込み時の警告もファイルに残すため)

        logger.info("起動します(版 %s、%s:%s)", __version__, config.server.host, config.server.port)
        # uvicorn のログも、上で整えた出力に流す(log_config=None)
        uvicorn.run(app, host=config.server.host, port=config.server.port, log_config=None)
    except SystemExit as e:
        if e.code not in (0, None):
            logger.error("起動できずに終了しました(終了コード %s)。理由は上のログを見てください", e.code)
        return e.code if isinstance(e.code, int) else 1
    except Exception:
        logger.exception("起動できませんでした")
        return 1
    finally:
        if lock is not None:
            lock.release()
    logger.info("停止しました")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
