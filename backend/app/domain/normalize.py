"""既存アプリと同じ、ファイルNo.と実装ラインの正規化。

既存アプリの models/production_side_master.py からの移植。既存アプリと完全に同じ結果になるよう、
処理を変えないこと(数字だけのファイルNo.は文字列のまま zfill し、int には変換しない)。
"""

from __future__ import annotations

import unicodedata


def normalize_setup_file_no(value) -> str:  # noqa: ANN001  既存アプリと同じく何でも受け取る
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if text.isdigit():
        return text.zfill(4)
    return text.upper()


def normalize_mounting_line(value) -> str:  # noqa: ANN001
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).strip().upper()
