"""計画と、計画の同期の記録のテーブル。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import TZDateTime

PLAN_ACTIVE = "active"
PLAN_CANCELLED = "cancelled"

SYNC_OK = "ok"
SYNC_ERROR = "error"
SYNC_SKIPPED = "skipped"
SYNC_GUARDED = "guarded"  # 一括取消の安全装置が働き、反映しなかった


class Plan(Base):
    """既存アプリから取得した計画(1行=1回)。行は消さず、取消は status で表す。"""

    __tablename__ = "plans"

    kitting_no: Mapped[str] = mapped_column(String, primary_key=True)
    lot_no: Mapped[str] = mapped_column(String, primary_key=True)
    file_no: Mapped[str] = mapped_column(String)
    line_code: Mapped[str] = mapped_column(String)
    product_name: Mapped[str] = mapped_column(String)
    run_no: Mapped[int] = mapped_column(Integer)  # 1=1回目、2=2回目(既存DBの面)
    planned_qty: Mapped[int] = mapped_column(Integer)
    cumulative_qty: Mapped[int | None] = mapped_column(Integer)
    order_qty: Mapped[int | None] = mapped_column(Integer)
    planned_start: Mapped[datetime | None] = mapped_column(TZDateTime)
    planned_end: Mapped[datetime | None] = mapped_column(TZDateTime)
    deadline: Mapped[datetime | None] = mapped_column(TZDateTime)
    delete_flag: Mapped[bool] = mapped_column(default=False)  # 保存するだけ。取消の判定には使わない
    # 想定タクト(master.db の production_side_master.takt_time。1枚あたりの秒)。マスタに無い・読めないときは None
    takt_sec: Mapped[float | None] = mapped_column(Float)
    # 正とした既存アプリの月次DBのフォルダ名(ロットごとに、最後に書き込まれたDB)
    source_db: Mapped[str | None] = mapped_column(String)
    # 既存DBの status 列の値(本アプリの status と区別するため legacy_ を付ける)
    legacy_status: Mapped[str | None] = mapped_column(String)
    legacy_plan_item_id: Mapped[int] = mapped_column(Integer)
    legacy_version: Mapped[int] = mapped_column(Integer)
    # キッティングNo.を分解した値
    issue_date: Mapped[date] = mapped_column(Date)
    issue_seq: Mapped[int] = mapped_column(Integer)
    # 本アプリでの状態
    status: Mapped[str] = mapped_column(String, default=PLAN_ACTIVE)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        Index("ix_plans_line_status_start", "line_code", "status", "planned_start"),
    )


class PlanSyncRun(Base):
    """計画の同期1回分の記録。"""

    __tablename__ = "plan_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(TZDateTime)
    finished_at: Mapped[datetime] = mapped_column(TZDateTime)
    result: Mapped[str] = mapped_column(String)  # ok / error / skipped / guarded
    added: Mapped[int] = mapped_column(Integer, default=0)
    revived: Mapped[int] = mapped_column(Integer, default=0)  # 取消から復活した計画(added とは別に数える)
    changed: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    cancelled: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    # その回に読んだ月次DBの一覧と、DBごとの計画の件数(JSON)。読む前に失敗した回は空
    legacy_dbs: Mapped[str | None] = mapped_column(Text)


class PlanSyncWarning(Base):
    """同期で見つかった警告(取り込めなかった行、面やラインの食い違いなど)。

    同じ (kitting_no, lot_no, message) の警告は1件にまとめ、出続けている間は last_seen_at を更新する。
    同期で出なくなったら resolved_at を入れ、再び出たら resolved_at を空に戻す。
    """

    __tablename__ = "plan_sync_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str | None] = mapped_column(String)
    lot_no: Mapped[str | None] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    # 最後に警告になった既存DBの行番号(キッティングNo.が空の行を探すときの手がかり)
    legacy_plan_item_id: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(TZDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(TZDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    __table_args__ = (
        Index("ix_plan_sync_warnings_key", "kitting_no", "lot_no"),
        Index("ix_plan_sync_warnings_resolved_at", "resolved_at"),
    )
