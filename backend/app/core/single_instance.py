"""同じ基準のフォルダ(同じDB)で、アプリが2つ動かないようにする。起動処理(バックアップとマイグレーション)の前に確かめる。

ロックは OS のファイルロック(Windows は msvcrt.locking)で取る。プロセスが落ちると OS が外すので、ロックが残り続けない。
詳細: docs/design/packaging.md
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import IO


class AlreadyRunning(Exception):
    """ほかのプロセスが、同じDBで動いている。"""


class InstanceLock:
    """data フォルダのロックファイル。acquire したプロセスが動いている間だけ持つ。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: IO[bytes] | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.path, "a+b")  # noqa: SIM115  ロックを持つ間は開いたままにする
        try:
            f.seek(0)
            _lock(f)
        except OSError as e:
            f.close()
            raise AlreadyRunning(f"ほかのプロセスが動いています(ロックファイル {self.path})") from e
        self._file = f

    def release(self) -> None:
        if self._file is not None:
            self._file.close()  # 閉じると OS がロックを外す
            self._file = None


if sys.platform == "win32":
    import msvcrt

    def _lock(f: IO[bytes]) -> None:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)  # 先頭の1バイト。取れなければすぐに OSError
else:
    import fcntl

    def _lock(f: IO[bytes]) -> None:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def port_available(host: str, port: int) -> bool:
    """そのポートで待ち受けられるか(実際に bind して、すぐ閉じる)。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if sys.platform == "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True
