"""本番の起動の入口(app/server.py)。

- ウィンドウを出さない exe でも、起動の失敗がログのファイルに残ること
- 同じDBでほかのプロセスが動いている・ポートが使用中なら、起動処理(バックアップとマイグレーション)の前に止まること
"""

import logging
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

from app import server
from app.core.config import get_config
from app.core.single_instance import AlreadyRunning, InstanceLock


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
    monkeypatch.setattr(sys, "stderr", None)  # ウィンドウを出さない exe と同じ
    (tmp_path / "data").mkdir()
    get_config.cache_clear()
    return tmp_path


@pytest.fixture
def old_db(home):
    """前の版のDB(マイグレーションの前の形)と、バックアップの設定。"""
    with closing(sqlite3.connect(home / "data" / "genba.db")) as c, c:
        c.execute("CREATE TABLE t (x INTEGER)")
    return home / "data" / "genba.db"


def _config(home, port=None, extra=""):
    port = port if port is not None else _free_port()
    (home / "data" / "config.toml").write_text(
        f'[server]\nhost = "127.0.0.1"\nport = {port}\n[paths]\nbackup_dir = "backup"\n{extra}', encoding="utf-8")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _log(home) -> str:
    for h in logging.getLogger().handlers:
        h.flush()
    return (home / "logs" / "genba.log").read_text(encoding="utf-8")


def _untouched(home, db) -> bool:
    """バックアップを取らず、マイグレーションもしていない。"""
    with closing(sqlite3.connect(db)) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return tables == {"t"} and not (home / "backup").exists()


def test_logging_works_without_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    server.setup_logging(tmp_path / "logs")
    logging.getLogger("x").warning("ファイルにだけ出る")
    assert "ファイルにだけ出る" in _log(tmp_path)


def test_broken_config_is_logged_to_file(home):
    (home / "data" / "config.toml").write_text("[server\nport = 1\n", encoding="utf-8")
    assert server.main() == 1
    log = _log(home)
    assert "起動できませんでした" in log and "config.toml の書き方に誤りがあります" in log


def test_second_instance_stops_before_backup_and_migration(home, old_db):
    _config(home)
    first = InstanceLock(home / "data" / "genba.lock")
    first.acquire()  # 1つ目が動いている
    try:
        assert server.main() == server.EXIT_ALREADY_RUNNING
    finally:
        first.release()
    assert "起動しません: ほかのプロセスが動いています" in _log(home)
    assert _untouched(home, old_db)


def test_port_in_use_stops_before_backup_and_migration(home, old_db):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        _config(home, port)
        assert server.main() == server.EXIT_PORT_IN_USE
    assert f"ポート {port} はほかのプログラムが使っています" in _log(home)
    assert _untouched(home, old_db)


def test_can_start_after_the_first_one_stopped(home, old_db, monkeypatch):
    _config(home)
    first = InstanceLock(home / "data" / "genba.lock")
    first.acquire()
    first.release()  # 1つ目が止まった
    started = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: started.append(kw["port"]))
    assert server.main() == 0
    assert len(started) == 1
    # 動いている間はロックを持ち、止まったら外す
    again = InstanceLock(home / "data" / "genba.lock")
    again.acquire()
    again.release()


def test_lock_is_held_while_running(tmp_path):
    lock = InstanceLock(tmp_path / "genba.lock")
    lock.acquire()
    with pytest.raises(AlreadyRunning):
        InstanceLock(tmp_path / "genba.lock").acquire()
    lock.release()


def test_lock_does_not_remain_after_a_crash(tmp_path):
    path = tmp_path / "genba.lock"
    code = (
        "import sys, time; sys.path.insert(0, sys.argv[2]);"
        "from pathlib import Path; from app.core.single_instance import InstanceLock;"
        "lock = InstanceLock(Path(sys.argv[1])); lock.acquire(); print('locked', flush=True); time.sleep(60)"
    )
    backend = str(Path(server.__file__).resolve().parents[1])
    child = subprocess.Popen([sys.executable, "-c", code, str(path), backend], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(AlreadyRunning):
            InstanceLock(path).acquire()
        child.kill()  # 異常終了(ロックを外す処理は動かない)
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
        child.stdout.close()
    # OS がロックを外している。Windows は、終了したプロセスのロックを少し遅れて外す
    # (venv の python.exe は本体を子プロセスで動かすので、本体の終了も少し遅れる)ため、数秒は待つ
    deadline = time.monotonic() + 10
    while True:
        try:
            InstanceLock(path).acquire()
            break
        except AlreadyRunning:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)
