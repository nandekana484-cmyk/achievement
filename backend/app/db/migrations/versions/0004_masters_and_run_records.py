"""マスタ(ライン・作業者・設備・理由)と、実績(今の担当者・工程・NG数と備考・完了・付帯作業)、冪等性の記録

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21

- 理由の初期データを入れる(開発指針 5.5)
- それまでに取り込んだ計画のラインを、lines に登録する(以後は計画の同期で自動登録)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (名前, 区分, 設備が必須, 理由の記入が必須, 付帯作業として使える, 再開理由として使える)
# counts_in_utilization は使わない(効率は理由によらず付帯作業の時間を分母に入れない。列は残す。詳細: docs/design/metrics.md)
REASONS = [
    ("部品探し", "loss", False, False, True, True),
    ("欠品", "loss", False, False, True, True),
    ("マシントラブル", "loss", True, False, True, True),
    ("立上立会", "non_loss", False, False, True, False),
    ("応援・その他", "non_loss", False, False, True, False),
    ("その他トラブル", "loss", False, True, True, True),
    ("人員交代", "non_loss", False, False, False, True),
    ("トラブル停止", "loss", False, False, False, True),
    ("計画切替", "non_loss", False, False, False, True),
]


def _master_columns() -> list[sa.Column]:
    return [
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    op.create_table(
        "lines",
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        *_master_columns(),
        sa.PrimaryKeyConstraint("line_code"),
    )
    op.create_table(
        "operators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        *_master_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        *_master_columns(),
        sa.ForeignKeyConstraint(["line_code"], ["lines.line_code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    reasons = op.create_table(
        "reasons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("counts_in_utilization", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_equipment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_text", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("usable_as_line_event", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("usable_as_restart", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_master_columns(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "line_operators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["line_code"], ["lines.line_code"]),
        sa.ForeignKeyConstraint(["operator_id"], ["operators.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ux_line_operators_current", "line_operators", ["line_code"], unique=True,
                    sqlite_where=sa.text("end_at IS NULL"))

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("step_type", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("started_by", sa.Integer(), nullable=False),
        sa.Column("ended_by", sa.Integer(), nullable=True),
        sa.Column("produced_qty", sa.Integer(), nullable=True),
        sa.Column("restart_reason_id", sa.Integer(), nullable=True),
        sa.Column("start_request_id", sa.String(), nullable=False),
        sa.Column("end_request_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        sa.ForeignKeyConstraint(["started_by"], ["operators.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["operators.id"]),
        sa.ForeignKeyConstraint(["restart_reason_id"], ["reasons.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("start_request_id"),
        sa.UniqueConstraint("end_request_id"),
        sa.UniqueConstraint("kitting_no", "lot_no", "step_type", "seq", name="uq_run_events_seq"),
    )
    op.create_index("ux_run_events_open", "run_events", ["kitting_no", "lot_no", "step_type"], unique=True,
                    sqlite_where=sa.text("end_at IS NULL"))

    op.create_table(
        "run_inputs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("entered_by", sa.Integer(), nullable=False),
        sa.Column("entered_at", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        sa.ForeignKeyConstraint(["entered_by"], ["operators.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_run_inputs_plan", "run_inputs", ["kitting_no", "lot_no", "kind"])

    op.create_table(
        "run_completions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kitting_no", sa.String(), nullable=False),
        sa.Column("lot_no", sa.String(), nullable=False),
        sa.Column("cleanup_event_id", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("produced_qty", sa.Integer(), nullable=False),
        sa.Column("ng_qty", sa.Integer(), nullable=True),
        sa.Column("plan_qty_snapshot", sa.Integer(), nullable=False),
        sa.Column("takt_sec_snapshot", sa.Float(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["kitting_no", "lot_no"], ["plans.kitting_no", "plans.lot_no"]),
        sa.ForeignKeyConstraint(["cleanup_event_id"], ["run_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cleanup_event_id"),
    )
    op.create_index("ix_run_completions_plan", "run_completions", ["kitting_no", "lot_no"])

    op.create_table(
        "line_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("line_code", sa.String(), nullable=False),
        sa.Column("reason_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("started_by", sa.Integer(), nullable=False),
        sa.Column("ended_by", sa.Integer(), nullable=True),
        sa.Column("start_request_id", sa.String(), nullable=False),
        sa.Column("end_request_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["line_code"], ["lines.line_code"]),
        sa.ForeignKeyConstraint(["reason_id"], ["reasons.id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"]),
        sa.ForeignKeyConstraint(["started_by"], ["operators.id"]),
        sa.ForeignKeyConstraint(["ended_by"], ["operators.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("start_request_id"),
        sa.UniqueConstraint("end_request_id"),
    )
    op.create_index("ix_line_events_line_start", "line_events", ["line_code", "start_at"])
    op.create_index("ux_line_events_open", "line_events", ["line_code", "reason_id"], unique=True,
                    sqlite_where=sa.text("end_at IS NULL"))

    op.create_table(
        "api_requests",
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
    )

    op.bulk_insert(reasons, [
        {
            "name": name, "category": category, "counts_in_utilization": False,
            "requires_equipment": equipment, "requires_text": text,
            "usable_as_line_event": line_event, "usable_as_restart": restart,
            "active": True, "sort_order": (i + 1) * 10,
        }
        for i, (name, category, equipment, text, line_event, restart) in enumerate(REASONS)
    ])

    # それまでに取り込んだ計画のライン(計画の line_code は正規化済み)
    bind = op.get_bind()
    codes = [r[0] for r in bind.execute(sa.text("SELECT DISTINCT line_code FROM plans ORDER BY line_code"))]
    for i, code in enumerate(codes):
        bind.execute(
            sa.text("INSERT INTO lines (line_code, name, active, sort_order) VALUES (:c, :n, 1, :s)"),
            {"c": code, "n": f"{code}ライン", "s": (i + 1) * 10},
        )


def downgrade() -> None:
    op.drop_table("api_requests")
    op.drop_index("ux_line_events_open", table_name="line_events")
    op.drop_index("ix_line_events_line_start", table_name="line_events")
    op.drop_table("line_events")
    op.drop_index("ix_run_completions_plan", table_name="run_completions")
    op.drop_table("run_completions")
    op.drop_index("ix_run_inputs_plan", table_name="run_inputs")
    op.drop_table("run_inputs")
    op.drop_index("ux_run_events_open", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ux_line_operators_current", table_name="line_operators")
    op.drop_table("line_operators")
    op.drop_table("reasons")
    op.drop_table("equipment")
    op.drop_table("operators")
    op.drop_table("lines")
