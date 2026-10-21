"""画面の確認用のデータ(開発用のコマンド demo-seed)。既存アプリのDBを使わない環境でだけ使う。

1回目と2回目の組、計画の時間の重なり、タクトなしの計画を含める。何度実行しても同じ結果になる。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_ACTIVE, Equipment, Operator, Plan
from app.db.session import write_transaction
from app.domain.kitting_no import parse_kitting_no
from app.domain.normalize import normalize_mounting_line
from app.services.masters import register_lines

DEMO_SOURCE = "demo"
OPERATORS = ("山田", "佐藤")
EQUIPMENT = ("マウンター1", "リフロー炉")


@dataclass(frozen=True)
class _DemoPlan:
    file_no: str
    run_no: int
    seq: int
    lot_no: str
    product_name: str
    qty: int
    takt_sec: float | None
    start: str  # HH:MM
    end: str


# (ファイルNo.、回、発行順、ロットNo.、品名、数量、タクト、計画開始、計画終了)
PLANS = (
    _DemoPlan("0722", 1, 1, "DEMO-001", "制御基板A", 300, 30.0, "08:00", "11:00"),
    _DemoPlan("0722", 2, 2, "DEMO-001", "制御基板A", 300, 55.72, "11:00", "14:00"),  # 上と組
    _DemoPlan("0800", 1, 3, "DEMO-002", "電源基板B", 120, None, "10:30", "12:30"),  # 重なり・タクトなし
    _DemoPlan("0915", 1, 4, "DEMO-003", "表示基板C", 500, 25.0, "14:00", "17:30"),
    _DemoPlan("0930", 1, 5, "DEMO-004", "通信基板D", 200, 40.0, "18:00", "20:00"),
)


def seed_demo(session: Session, line_code: str, day: dt.date) -> list[str]:
    """確認用の計画・作業者・設備を入れ、入れた(または更新した)計画のキッティングNo.を返す。"""
    line = normalize_mounting_line(line_code)
    issue = day - dt.timedelta(days=7)
    with write_transaction(session):
        register_lines(session, [line])
        session.flush()
        for i, name in enumerate(OPERATORS):
            if session.scalars(select(Operator).where(Operator.name == name)).first() is None:
                session.add(Operator(name=name, active=True, sort_order=(i + 1) * 10))
        for i, name in enumerate(EQUIPMENT):
            exists = session.scalars(select(Equipment).where(Equipment.line_code == line, Equipment.name == name)).first()
            if exists is None:
                session.add(Equipment(line_code=line, name=name, active=True, sort_order=(i + 1) * 10))
        knos = [_upsert_plan(session, p, line, day, issue) for p in PLANS]
        session.commit()
    return knos


def _upsert_plan(session: Session, p: _DemoPlan, line: str, day: dt.date, issue: dt.date) -> str:
    kno = f"{p.file_no}-{p.run_no}-{line}-{issue:%y%m%d}-{p.seq:02d}"
    parsed = parse_kitting_no(kno)
    now = clock.now()
    row = session.get(Plan, (kno, p.lot_no))
    if row is None:
        row = Plan(kitting_no=kno, lot_no=p.lot_no, first_seen_at=now)
        session.add(row)
    row.file_no, row.line_code, row.product_name, row.run_no = p.file_no, line, p.product_name, p.run_no
    row.planned_qty, row.cumulative_qty, row.order_qty, row.takt_sec = p.qty, 0, p.qty, p.takt_sec
    row.planned_start, row.planned_end = _at(day, p.start), _at(day, p.end)
    row.deadline = _at(day + dt.timedelta(days=3), "17:00")
    row.delete_flag, row.legacy_status, row.source_db = False, None, DEMO_SOURCE
    row.legacy_plan_item_id, row.legacy_version = 0, 0
    row.issue_date, row.issue_seq = parsed.issue_date, parsed.issue_seq
    row.status, row.cancelled_at, row.updated_at = PLAN_ACTIVE, None, now
    return kno


def _at(day: dt.date, hm: str) -> dt.datetime:
    h, m = (int(x) for x in hm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m), tzinfo=clock.JST)
