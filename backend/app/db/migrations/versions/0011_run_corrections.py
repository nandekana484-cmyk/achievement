"""実績の訂正: 訂正の履歴(run_corrections)、取り消しの印と後からの追加の印、完了の作り直し

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-22

- run_events / line_events に取り消しの印(voided_at・voided_by・void_reason)を足す。run_events には後からの追加の印も
- 「終了していない記録は1件まで」の一意制約から、取り消した記録を除く
- run_completions は、訂正で作り直した行が同じ片付けを参照するので cleanup_event_id の一意制約を外す。
  SQLite では列の一意制約だけを外せないため、新しい表を作って写す(run_completions を参照する表は無い)

詳細: docs/design/run-records.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPLETION_COLUMNS = ("id, kitting_no, cleanup_event_id, completed_at, produced_qty, plan_qty_snapshot, takt_sec_snapshot,"
                       " lots_snapshot, ng_snapshot, utilization")


def _void_columns(table: str) -> None:
    op.add_column(table, sa.Column("voided_at", sa.DateTime(), nullable=True))
    # 外部キーの付いた列を ALTER TABLE で足す(SQLite は既定値が NULL なら許す。Alembic の add_column では付けられない)
    op.execute(f"ALTER TABLE {table} ADD COLUMN voided_by INTEGER CONSTRAINT fk_{table}_voided_by REFERENCES operators (id)")
    op.add_column(table, sa.Column("void_reason", sa.String(), nullable=True))


def _open_index(name: str, table: str, columns: list[str], where: str) -> None:
    op.drop_index(name, table_name=table)
    op.create_index(name, table, columns, unique=True, sqlite_where=sa.text(where))


def _create_corrections() -> None:
    op.create_table(
        "run_corrections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_table", sa.String(), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=True),
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("changes_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("corrected_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("corrected_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False, unique=True),
    )
    op.create_index("ix_run_corrections_kitting", "run_corrections", ["kitting_no"])
    op.create_index("ix_run_corrections_target", "run_corrections", ["target_table", "target_id"])


def _rebuild_completions(with_correction: bool) -> None:
    extra = [
        sa.Column("kind", sa.String(), nullable=False, server_default="cleanup"),
        sa.Column("correction_id", sa.Integer(), sa.ForeignKey("run_corrections.id"), nullable=True),
    ] if with_correction else []
    op.create_table(
        "run_completions_v11",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("cleanup_event_id", sa.Integer(), sa.ForeignKey("run_events.id"), nullable=False,
                  unique=not with_correction),
        *extra,
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("produced_qty", sa.Integer(), nullable=False),
        sa.Column("plan_qty_snapshot", sa.Integer(), nullable=False),
        sa.Column("takt_sec_snapshot", sa.Float(), nullable=True),
        sa.Column("lots_snapshot", sa.Text(), nullable=True),
        sa.Column("ng_snapshot", sa.Text(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
    )
    op.execute(f"INSERT INTO run_completions_v11 ({_COMPLETION_COLUMNS}) SELECT {_COMPLETION_COLUMNS} FROM run_completions")
    op.drop_index("ix_run_completions_kitting", table_name="run_completions")
    op.drop_table("run_completions")
    op.rename_table("run_completions_v11", "run_completions")
    op.create_index("ix_run_completions_kitting", "run_completions", ["kitting_no"])


def upgrade() -> None:
    _void_columns("run_events")
    op.add_column("run_events", sa.Column("added_later", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    _void_columns("line_events")
    _open_index("ux_run_events_open", "run_events", ["kitting_no", "step_type"], "end_at IS NULL AND voided_at IS NULL")
    _open_index("ux_line_events_open", "line_events", ["line_code", "reason_id"], "end_at IS NULL AND voided_at IS NULL")
    _create_corrections()
    _rebuild_completions(with_correction=True)


def downgrade() -> None:
    # 作り直した完了の行は、片付けの記録との一意制約に当たるので消す(戻すのは開発用)
    op.execute("DELETE FROM run_completions WHERE kind = 'correction'")
    _rebuild_completions(with_correction=False)
    op.drop_index("ix_run_corrections_target", table_name="run_corrections")
    op.drop_index("ix_run_corrections_kitting", table_name="run_corrections")
    op.drop_table("run_corrections")
    _open_index("ux_line_events_open", "line_events", ["line_code", "reason_id"], "end_at IS NULL")
    _open_index("ux_run_events_open", "run_events", ["kitting_no", "step_type"], "end_at IS NULL")
    for table in ("line_events", "run_events"):
        with op.batch_alter_table(table) as batch:
            if table == "run_events":
                batch.drop_column("added_later")
            batch.drop_column("void_reason")
            batch.drop_column("voided_by")
            batch.drop_column("voided_at")
