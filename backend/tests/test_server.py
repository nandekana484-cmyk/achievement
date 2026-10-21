"""本番の起動の入口(app/server.py)。ウィンドウを出さない exe でも、起動の失敗がログのファイルに残ること。"""

import logging
import socket
import sys

import pytest

from app import server
from app.core.config import get_config


@pytest.fixture(autouse=True)
def restore_logging():
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    yield
    for h in root.handlers:
        if h not in saved[0]:
            h.close()
    root.handlers[:] = saved[0]
    root.setLevel(saved[1])
    get_config.cache_clear()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("GENBA_HOME", str(tmp_path))
    monkeypatch.delenv("GENBA_CONFIG", raising=False)
    (tmp_path / "data").mkdir()
    get_config.cache_clear()
    return tmp_path


def _log(home) -> str:
    for h in logging.getLogger().handlers:
        h.flush()
    return (home / "logs" / "genba.log").read_text(encoding="utf-8")


def test_logging_works_without_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)  # ウィンドウを出さない exe と同じ
    server.setup_logging(tmp_path / "logs")
    logging.getLogger("x").warning("ファイルにだけ出る")
    assert "ファイルにだけ出る" in _log(tmp_path)


def test_broken_config_is_logged_to_file(home, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    (home / "data" / "config.toml").write_text("[server\nport = 1\n", encoding="utf-8")
    assert server.main() == 1
    log = _log(home)
    assert "起動できませんでした" in log and "config.toml の書き方に誤りがあります" in log


def test_port_in_use_is_logged_to_file(home, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        (home / "data" / "config.toml").write_text(
            f'[server]\nhost = "127.0.0.1"\nport = {port}\n', encoding="utf-8")
        assert server.main() != 0  # uvicorn は起動の失敗を終了コード 3 で返す
    log = _log(home)
    assert "起動できずに終了しました" in log
    assert str(port) in log  # uvicorn が出す理由(使用中のポート)も残る
