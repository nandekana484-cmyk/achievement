"""実績(今の担当者・工程・NG数と備考・完了・付帯作業)と、冪等性の記録のテーブル。物理削除しない。

詳細: docs/design/run-records.md
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime


class LineOperator(Base):
    """ラインの今の担当者とその履歴。交代すると前の行に end_at を入れる。"""

    __tablename__ = "line_operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_code: Mapped[str] = mapped_column(String, ForeignKey("lines.line_code"))
    operator_id: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    start_at: Mapped[datetime] = mapped_column(TZDateTime)
    end_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    request_id: Mapped[str | None] = mapped_column(String, unique=True)

    __table_args__ = (
        # 今の担当者はラインに1人
        Index("ux_line_operators_current", "line_code", unique=True, sqlite_where=text("end_at IS NULL")),
    )


class RunEvent(Base):
    """工程と生産の区切りの記録(キッティングNo.の単位)。seq はキッティングNo.×工程ごとに1から振る。"""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    step_type: Mapped[str] = mapped_column(String)
    seq: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(TZDateTime)
    end_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    started_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    ended_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("operators.id"))
    produced_qty: Mapped[int | None] = mapped_column(Integer)  # 生産の区切りの生産数
    restart_reason_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reasons.id"))
    # 設備が必要な再開理由(マシントラブルなど)を選んだときの設備(任意)
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment.id", name="fk_run_events_equipment_id"))
    start_request_id: Mapped[str] = mapped_column(String, unique=True)
    end_request_id: Mapped[str | None] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime)

    __table_args__ = (
        UniqueConstraint("kitting_no", "step_type", "seq", name="uq_run_events_seq"),
        # 同じキッティングNo.の同じ工程で、終了していない記録は1件まで(二重開始をDBでも防ぐ)
        Index("ux_run_events_open", "kitting_no", "step_type", unique=True, sqlite_where=text("end_at IS NULL")),
    )


class RunInput(Base):
    """時刻を持たない入力のうち、NG数以外(今は備考)。キッティングNo.の単位。"""

    __tablename__ = "run_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # remark
    value: Mapped[str] = mapped_column(Text)
    entered_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    entered_at: Mapped[datetime] = mapped_column(TZDateTime)
    request_id: Mapped[str] = mapped_column(String, unique=True)

    __table_args__ = (Index("ix_run_inputs_kitting", "kitting_no", "kind"),)


class RunNgInput(Base):
    """NG数。ロットと、NGが出た面を選んで入力する。同じ (kitting_no, lot_no, side) は最新の値を有効とする。"""

    __tablename__ = "run_ng_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)  # 入力した画面の計画
    lot_no: Mapped[str] = mapped_column(String)
    side: Mapped[int] = mapped_column(Integer)  # NGが出た面(1 / 2)
    side_kitting_no: Mapped[str] = mapped_column(String)  # NGが出た面の計画のキッティングNo.(既存アプリに返すときに使う)
    ng_qty: Mapped[int] = mapped_column(Integer)
    entered_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    entered_at: Mapped[datetime] = mapped_column(TZDateTime)
    request_id: Mapped[str] = mapped_column(String, unique=True)

    __table_args__ = (Index("ix_run_ng_inputs_key", "kitting_no", "lot_no", "side"),)


class RunCompletion(Base):
    """完了時点の確定値(キッティングNo.の単位)。片付けの終了で1件作る(やり直したらもう1件。最新を有効とする)。"""

    __tablename__ = "run_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    cleanup_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_events.id"), unique=True)
    completed_at: Mapped[datetime] = mapped_column(TZDateTime)
    produced_qty: Mapped[int] = mapped_column(Integer)  # 生産の区切りの合計
    plan_qty_snapshot: Mapped[int] = mapped_column(Integer)  # ロットの数量の合計
    takt_sec_snapshot: Mapped[float | None] = mapped_column(Float)
    lots_snapshot: Mapped[str | None] = mapped_column(Text)  # JSON: [{lot_no, product_name, planned_qty}]
    ng_snapshot: Mapped[str | None] = mapped_column(Text)  # JSON: ロットと面ごとの最新のNG数
    # TODO(要確認): 稼働率の定義(今は計算しない)
    utilization: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_run_completions_kitting", "kitting_no"),)


class LineEvent(Base):
    """付帯作業(ライン単位。計画には結びつけない)。"""

    __tablename__ = "line_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_code: Mapped[str] = mapped_column(String, ForeignKey("lines.line_code"))
    reason_id: Mapped[int] = mapped_column(Integer, ForeignKey("reasons.id"))
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment.id"))
    reason_text: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(TZDateTime)
    end_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    started_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    ended_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("operators.id"))
    start_request_id: Mapped[str] = mapped_column(String, unique=True)
    end_request_id: Mapped[str | None] = mapped_column(String, unique=True)

    __table_args__ = (
        Index("ix_line_events_line_start", "line_code", "start_at"),
        # 同じラインで同じ理由の付帯作業は、終了していないものが1件まで
        Index("ux_line_events_open", "line_code", "reason_id", unique=True, sqlite_where=text("end_at IS NULL")),
    )


class ApiRequest(Base):
    """ボタン操作の冪等性のための記録(開発指針 0-5)。

    同じ request_id の再送には、最初の応答(response)をそのまま返す。内容(payload)が違えば拒否する。
    """

    __tablename__ = "api_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    operation: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)  # JSON
    response: Mapped[str] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(TZDateTime)
