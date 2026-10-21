"""実績をキッティングNo.の単位にする(工程・備考・完了から lot_no を外す)。NG はロットと面を持つ run_ng_inputs に分ける

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-21

本番にはまだ入れていないので、開発用の記録を移すだけ。同じキッティングNo.に複数のロットの工程の記録がある
(まとめると重なる)場合は、作り直さずに止める(手で確かめるため)。
SQLite で外部キー(plans への複合キー)を外すため、新しい表を作って写し、古い表を消してから名前を戻す。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stop_if_overlapping() -> None:
    rows = op.get_bind().execute(sa.text(
        "SELECT kitting_no FROM run_events GROUP BY kitting_no HAVING COUNT(DISTINCT lot_no) > 1"
    )).all()
    if rows:
        knos = ", ".join(r[0] for r in rows)
        raise RuntimeError(f"同じキッティングNo.に複数のロットの工程の記録があります(まとめると重なる): {knos}")


def _create_new_tables() -> None:
    op.create_table(
        "run_events_v6",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("started_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("ended_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=True),
        sa.Column("produced_qty", sa.Integer(), nullable=True),
        sa.Column("restart_reason_id", sa.Integer(), sa.ForeignKey("reasons.id"), nullable=True),
        sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("equipment.id", name="fk_run_events_equipment_id"), nullable=True),
        sa.Column("start_request_id", sa.String(), nullable=False, unique=True),
        sa.Column("end_request_id", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kitting_no", "step_type", "seq", name="uq_run_events_seq"),
    )
    op.create_table(
        "run_completions_v6",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        # 名前を戻すと、参照先も run_events に書き換わる
        sa.Column("cleanup_event_id", sa.Integer(), sa.ForeignKey("run_events_v6.id"), nullable=False, unique=True),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("produced_qty", sa.Integer(), nullable=False),
        sa.Column("plan_qty_snapshot", sa.Integer(), nullable=False),
        sa.Column("takt_sec_snapshot", sa.Float(), nullable=True),
        sa.Column("lots_snapshot", sa.Text(), nullable=True),
        sa.Column("ng_snapshot", sa.Text(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "run_inputs_v6",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("entered_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("entered_at", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False, unique=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "run_ng_inputs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("side", sa.Integer(), nullable=False),
        sa.Column("side_kitting_no", sa.String(), nullable=False),
        sa.Column("ng_qty", sa.Integer(), nullable=False),
        sa.Column("entered_by", sa.Integer(), sa.ForeignKey("operators.id"), nullable=False),
        sa.Column("entered_at", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False, unique=True),
        sa.PrimaryKeyConstraint("id"),
    )


_COPY = [
    """INSERT INTO run_events_v6 (id, kitting_no, step_type, seq, start_at, end_at, started_by, ended_by, produced_qty,
                                  restart_reason_id, equipment_id, start_request_id, end_request_id, created_at)
       SELECT id, kitting_no, step_type, seq, start_at, end_at, started_by, ended_by, produced_qty,
              restart_reason_id, equipment_id, start_request_id, end_request_id, created_at FROM run_events""",
    """INSERT INTO run_completions_v6 (id, kitting_no, cleanup_event_id, completed_at, produced_qty, plan_qty_snapshot,
                                       takt_sec_snapshot, utilization)
       SELECT id, kitting_no, cleanup_event_id, completed_at, produced_qty, plan_qty_snapshot, takt_sec_snapshot, utilization
         FROM run_completions""",
    """INSERT INTO run_inputs_v6 (id, kitting_no, kind, value, entered_by, entered_at, request_id)
       SELECT id, kitting_no, kind, value, entered_by, entered_at, request_id FROM run_inputs WHERE kind = 'remark'""",
    # それまでのNG数は、計画の面でNGが出たものとして移す
    """INSERT INTO run_ng_inputs (kitting_no, lot_no, side, side_kitting_no, ng_qty, entered_by, entered_at, request_id)
       SELECT i.kitting_no, i.lot_no, p.run_no, i.kitting_no, CAST(i.value AS INTEGER), i.entered_by, i.entered_at, i.request_id
         FROM run_inputs i JOIN plans p ON p.kitting_no = i.kitting_no AND p.lot_no = i.lot_no
        WHERE i.kind = 'ng_qty'""",
]


def upgrade() -> None:
    _stop_if_overlapping()
    _create_new_tables()
    for sql in _COPY:
        op.execute(sql)
    # 参照している表から消す(run_completions → run_events)
    for name in ("run_completions", "run_inputs", "run_events"):
        op.drop_table(name)
    for name in ("run_events", "run_completions", "run_inputs"):
        op.rename_table(f"{name}_v6", name)
    op.create_index("ux_run_events_open", "run_events", ["kitting_no", "step_type"], unique=True,
                    sqlite_where=sa.text("end_at IS NULL"))
    op.create_index("ix_run_inputs_kitting", "run_inputs", ["kitting_no", "kind"])
    op.create_index("ix_run_completions_kitting", "run_completions", ["kitting_no"])
    op.create_index("ix_run_ng_inputs_key", "run_ng_inputs", ["kitting_no", "lot_no", "side"])


def downgrade() -> None:
    raise NotImplementedError("0006 は戻せません(ロットNo.を持たない記録を、ロットの単位に分けられないため)")
