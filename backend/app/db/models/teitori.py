"""丁取り(既存アプリの master.db のビュー v_board_teitori)の写し。同期のたびに上書きする。

詳細: docs/design/metrics.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class BoardTeitori(Base):
    """(ファイルNo., 実装ライン) ごとの丁取り数。面は問わない(面1と面2は同じ丁取り)。キーは正規化した値。"""

    __tablename__ = "board_teitori"

    setup_file_no: Mapped[str] = mapped_column(String, primary_key=True)
    mounting_line: Mapped[str] = mapped_column(String, primary_key=True)
    teitori: Mapped[int | None] = mapped_column(Integer)  # status が ok のときだけ、1以上の整数
    status: Mapped[str] = mapped_column(String)  # ok / tsv_not_found / ... 知らない値も、そのまま持つ
    part_no: Mapped[str | None] = mapped_column(String)
    fetched_at: Mapped[str | None] = mapped_column(String)  # 既存アプリが引いた日時(そのPCのローカル時刻の文字列のまま)
    synced_at: Mapped[datetime] = mapped_column(TZDateTime)  # 本アプリが読み込んだ日時
