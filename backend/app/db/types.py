"""DBの列の型。

SQLite は時刻帯を保持しないので、日本時間に直した値をそのまま保存し、読み出すときに
日本時間(+09:00)を付け直す(開発指針 8: 時刻はタイムゾーン付き(日本時間)で保存する)。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

from app.core.clock import JST


class TZDateTime(TypeDecorator):
    """タイムゾーン付きの日時。保存時は日本時間に直し、読み出すと +09:00 が付く。"""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"タイムゾーンのない日時は保存できません: {value!r}")
        return value.astimezone(JST).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):  # noqa: ANN001
        if value is None:
            return None
        return value.replace(tzinfo=JST)
