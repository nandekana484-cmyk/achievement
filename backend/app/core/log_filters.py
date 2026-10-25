"""アクセスログ(uvicorn.access)から、個人を特定できる値を隠す(S-13)。詳細: docs/design/security.md

URL のクエリにある作業者ID(/api/operators/lookup?worker_id=…)などの値を「***」にする。パスと、ほかのクエリは残す。
"""

from __future__ import annotations

import logging
import re

SENSITIVE_QUERY_KEYS = ("worker_id", "password", "token")
_PATTERN = re.compile(r"(?i)([?&](?:" + "|".join(SENSITIVE_QUERY_KEYS) + r")=)[^&\s]*")


def mask_query(url: str) -> str:
    return _PATTERN.sub(r"\1***", url)


class MaskAccessLog(logging.Filter):
    """uvicorn のアクセスログの引数(接続元、メソッド、パス+クエリ、HTTPの版、状態)のうち、パス+クエリを直す。"""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], mask_query(args[2]), *args[3:])
        return True


def install_access_log_filter() -> None:
    """uvicorn.access に1回だけ付ける。"""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, MaskAccessLog) for f in logger.filters):
        logger.addFilter(MaskAccessLog())
