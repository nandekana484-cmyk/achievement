"""本アプリのDBのテーブル(開発指針 8)。

列を変えたら、マイグレーション(app/db/migrations/versions)を追加すること。
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
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
    # 想定タクト(master.db の production_side_master.takt_time)。マスタに無い・読めないときは None
    # TODO(要確認): 想定タクトの単位(今は「1枚あたりの秒」と仮定)
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


# --- マスタ(開発指針 7.2)。行は消さず、使わなくなったものは active=False にする ---


class Line(Base):
    """ライン。計画の同期で新しいラインの記号を見つけたら自動で登録する。"""

    __tablename__ = "lines"

    line_code: Mapped[str] = mapped_column(String, primary_key=True)  # 正規化した値
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Operator(Base):
    """作業者。"""

    __tablename__ = "operators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Equipment(Base):
    """設備(ラインごと)。"""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_code: Mapped[str] = mapped_column(String, ForeignKey("lines.line_code"))
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Reason(Base):
    """理由(付帯作業の種類と、生産の再開理由の共通マスタ。開発指針 5.5)。"""

    __tablename__ = "reasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)  # loss=ロス / non_loss=ロス以外
    # TODO(要確認): 付帯作業を稼働率に含めるか(今はすべて含めない)
    counts_in_utilization: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_equipment: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_text: Mapped[bool] = mapped_column(Boolean, default=False)
    usable_as_line_event: Mapped[bool] = mapped_column(Boolean, default=False)  # 付帯作業として使える
    usable_as_restart: Mapped[bool] = mapped_column(Boolean, default=False)  # 生産の再開理由として使える
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


# --- 実績(開発指針 5.4〜5.7)。物理削除しない。時刻はすべてサーバーの clock.now() ---


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
    """工程と生産の区切りの記録。seq は計画×工程ごとに1から振る。"""

    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    lot_no: Mapped[str] = mapped_column(String)
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
        ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        UniqueConstraint("kitting_no", "lot_no", "step_type", "seq", name="uq_run_events_seq"),
        # 同じ計画の同じ工程で、終了していない記録は1件まで(二重開始をDBでも防ぐ)
        Index("ux_run_events_open", "kitting_no", "lot_no", "step_type", unique=True,
              sqlite_where=text("end_at IS NULL")),
    )


class RunInput(Base):
    """時刻を持たない入力(NG数・備考)。NG数は行を追加し、最新の値を有効とする。"""

    __tablename__ = "run_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    lot_no: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # ng_qty / remark
    value: Mapped[str] = mapped_column(Text)
    entered_by: Mapped[int] = mapped_column(Integer, ForeignKey("operators.id"))
    entered_at: Mapped[datetime] = mapped_column(TZDateTime)
    request_id: Mapped[str] = mapped_column(String, unique=True)

    __table_args__ = (
        ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        Index("ix_run_inputs_plan", "kitting_no", "lot_no", "kind"),
    )


class RunCompletion(Base):
    """完了時点の確定値。片付けの終了で1件作る(やり直したらもう1件。最新のものを有効とする)。"""

    __tablename__ = "run_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kitting_no: Mapped[str] = mapped_column(String)
    lot_no: Mapped[str] = mapped_column(String)
    cleanup_event_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_events.id"), unique=True)
    completed_at: Mapped[datetime] = mapped_column(TZDateTime)
    produced_qty: Mapped[int] = mapped_column(Integer)  # 生産の区切りの合計
    ng_qty: Mapped[int | None] = mapped_column(Integer)  # その時点の最新のNG数
    plan_qty_snapshot: Mapped[int] = mapped_column(Integer)
    takt_sec_snapshot: Mapped[float | None] = mapped_column(Float)
    # TODO(要確認): 稼働率の定義(今は計算しない)
    utilization: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        Index("ix_run_completions_plan", "kitting_no", "lot_no"),
    )


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
