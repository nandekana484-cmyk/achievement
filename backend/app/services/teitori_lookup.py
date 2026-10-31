"""丁取りの写し(board_teitori)から、(ファイルNo., 実装ライン)の丁取り数を引く。詳細: docs/design/metrics.md"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import BoardTeitori
from app.integration.legacy.teitori import STATUS_OK

STATUS_NO_ROW = "no_row"  # 丁取りの行が無い(まだ引けていない組)。知らない status も、丁取り数は使わず「不明」として扱う


def lookup_teitori(session: Session, file_no: str, line_code: str) -> tuple[int | None, str]:
    """(丁取り数, status)。plans の file_no・line_code は正規化済みなので、そのまま主キーで引ける。"""
    row = session.get(BoardTeitori, (file_no, line_code))
    if row is None:
        return None, STATUS_NO_ROW
    return (row.teitori if row.status == STATUS_OK else None), row.status
