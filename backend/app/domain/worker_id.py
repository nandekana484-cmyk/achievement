"""作業者IDの正規化。既存アプリ(models/workers.py)と同じく、全角・半角と大文字・小文字の違いを無視して比べる。

IDの表記は入力したまま保存し、比べるときだけこの形にする。
"""

from __future__ import annotations

import unicodedata

MAX_LENGTH = 32  # 既存アプリの作業者IDの上限


def worker_key(worker_id: str | None) -> str:
    """比べるための形: 全角→半角(NFKC)、前後の空白を除く、大文字・小文字を区別しない(casefold)。"""
    return unicodedata.normalize("NFKC", worker_id or "").strip().casefold()
