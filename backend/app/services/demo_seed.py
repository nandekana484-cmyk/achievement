"""画面の確認用のデータ(開発用のコマンド demo-seed)。既存アプリのDBを使わない環境でだけ使う。

1回目と2回目の組、計画の時間の重なり、タクトなし、日付をまたぐ計画、次の稼働日の計画、表示範囲の終わりをまたぐ計画、
過ぎて未着手の計画、複数ロットのキッティングNo.(面1と面2の組)を含める。
何度実行しても同じ結果になる。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_ACTIVE, BoardTeitori, Equipment, Operator, Plan
from app.db.session import write_transaction
from app.domain.kitting_no import parse_kitting_no
from app.domain.normalize import normalize_mounting_line
from app.domain.worker_id import worker_key
from app.services.masters import register_lines

DEMO_SOURCE = "demo"
# (名前, 作業者ID)。同じ名前の人がいても区別できることを確かめるため、山田を2人入れる
OPERATORS = (("山田", "Y001", "operator"), ("佐藤", "S002", "operator"), ("山田", "Y015", "operator"),
             ("管理 花子", "A001", "admin"))  # 管理画面の確認用(パスワードは admin set-password で別に設定する)
EQUIPMENT = ("マウンター1", "リフロー炉")
# ファイルNo. → (丁取り数, status)。効率の計算から外れる計画(丁取りが引けない・タクトなし)も確かめられるようにする
TEITORI: dict[str, tuple[int | None, str]] = {
    "0722": (2, "ok"), "0800": (None, "tsv_not_found"), "0915": (4, "ok"), "0930": (1, "ok"), "0940": (None, "no_k_row"),
    "0950": (2, "ok"), "0960": (2, "ok"), "1000": (3, "ok"),
}


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
    end: str  # HH:MM。計画開始より前なら翌日
    day_offset: int = 0  # 指定した日からの日数


# (ファイルNo.、回、発行順、ロットNo.、品名、数量、タクト、計画開始、計画終了、日数)
PLANS = (
    _DemoPlan("0722", 1, 1, "DEMO-001", "制御基板A", 300, 30.0, "08:30", "11:30"),
    _DemoPlan("0722", 2, 2, "DEMO-001", "制御基板A", 300, 55.72, "11:30", "14:30"),  # 上と組
    _DemoPlan("0800", 1, 3, "DEMO-002", "電源基板B", 120, None, "10:30", "12:30"),  # 重なり・タクトなし
    _DemoPlan("0915", 1, 4, "DEMO-003", "表示基板C", 500, 25.0, "14:30", "18:00"),
    _DemoPlan("0930", 1, 5, "DEMO-004", "通信基板D", 200, 40.0, "22:00", "02:00"),  # 日付をまたぐ
    _DemoPlan("0940", 1, 6, "DEMO-005", "入力基板E", 150, 35.0, "08:30", "10:30", 1),  # 次の稼働日(境目の先)
    _DemoPlan("0960", 1, 8, "DEMO-007", "検査基板G", 100, 30.0, "18:00", "22:00", 1),  # 表示範囲の終わりをまたぐ
    _DemoPlan("0950", 1, 7, "DEMO-006", "試作基板F", 80, 30.0, "09:00", "12:00", -3),  # 過ぎて未着手(検索で選ぶ)
    # 1つのキッティングNo.に複数のロット(面1と面2の組)
    _DemoPlan("1000", 1, 9, "DEMO-101", "多ロット基板H1", 150, 32.0, "12:30", "14:30"),
    _DemoPlan("1000", 1, 9, "DEMO-102", "多ロット基板H2", 100, 32.0, "12:30", "14:30"),
    _DemoPlan("1000", 1, 9, "DEMO-103", "多ロット基板H3", 50, 32.0, "12:30", "14:30"),
    _DemoPlan("1000", 2, 10, "DEMO-101", "多ロット基板H1", 150, 40.0, "15:00", "17:00"),
    _DemoPlan("1000", 2, 10, "DEMO-102", "多ロット基板H2", 100, 40.0, "15:00", "17:00"),
    _DemoPlan("1000", 2, 10, "DEMO-103", "多ロット基板H3", 50, 40.0, "15:00", "17:00"),
)


def seed_demo(session: Session, line_code: str, day: dt.date, lot_suffix: str = "") -> list[str]:
    """確認用の計画・作業者・設備を入れ、入れた(または更新した)計画のキッティングNo.を返す。

    lot_suffix はロットNo.の末尾に付ける(ほかのラインと同じロットNo.にならないように。面1と面2のひも付けの確認用)。
    """
    line = normalize_mounting_line(line_code)
    issue = day - dt.timedelta(days=7)
    with write_transaction(session):
        register_lines(session, [line])
        session.flush()
        for i, (name, wid, role) in enumerate(OPERATORS):
            if session.scalars(select(Operator).where(Operator.worker_key == worker_key(wid))).first() is None:
                session.add(Operator(name=name, worker_id=wid, worker_key=worker_key(wid), role=role, source="local",
                                     active=True, sort_order=(i + 1) * 10))
        for i, name in enumerate(EQUIPMENT):
            exists = session.scalars(select(Equipment).where(Equipment.line_code == line, Equipment.name == name)).first()
            if exists is None:
                session.add(Equipment(line_code=line, name=name, active=True, sort_order=(i + 1) * 10))
        knos = [_upsert_plan(session, p, line, day, issue, lot_suffix) for p in PLANS]
        _upsert_teitori(session, line)
        session.commit()
    return knos


def _upsert_plan(session: Session, p: _DemoPlan, line: str, day: dt.date, issue: dt.date, lot_suffix: str) -> str:
    kno = f"{p.file_no}-{p.run_no}-{line}-{issue:%y%m%d}-{p.seq:02d}"
    parsed = parse_kitting_no(kno)
    now = clock.now()
    lot_no = p.lot_no + lot_suffix
    row = session.get(Plan, (kno, lot_no))
    if row is None:
        row = Plan(kitting_no=kno, lot_no=lot_no, first_seen_at=now)
        session.add(row)
    row.file_no, row.line_code, row.product_name, row.run_no = p.file_no, line, p.product_name, p.run_no
    row.planned_qty, row.cumulative_qty, row.order_qty, row.takt_sec = p.qty, 0, p.qty, p.takt_sec
    start_day = day + dt.timedelta(days=p.day_offset)
    row.planned_start = _at(start_day, p.start)
    row.planned_end = _at(start_day + dt.timedelta(days=1 if p.end <= p.start else 0), p.end)
    row.deadline = _at(start_day + dt.timedelta(days=3), "17:00")
    row.delete_flag, row.legacy_status, row.source_db = False, None, DEMO_SOURCE
    row.legacy_plan_item_id, row.legacy_version = 0, 0
    row.issue_date, row.issue_seq = parsed.issue_date, parsed.issue_seq
    row.status, row.cancelled_at, row.updated_at = PLAN_ACTIVE, None, now
    return kno


def _upsert_teitori(session: Session, line: str) -> None:
    now = clock.now()
    for file_no, (teitori, status) in TEITORI.items():
        row = session.get(BoardTeitori, (file_no, line))
        if row is None:
            row = BoardTeitori(setup_file_no=file_no, mounting_line=line)
            session.add(row)
        row.teitori, row.status, row.part_no, row.fetched_at, row.synced_at = teitori, status, None, None, now


def _at(day: dt.date, hm: str) -> dt.datetime:
    h, m = (int(x) for x in hm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m), tzinfo=clock.JST)
