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
from app.db.models import PLAN_ACTIVE, BoardTeitori, Equipment, Operator, Plan, RunEvent
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
    "0950": (2, "ok"), "0960": (2, "ok"), "1000": (3, "ok"), "1100": (2, "ok"), "1101": (2, "ok"), "1102": (2, "ok"), "1200": (2, "ok"),
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


def seed_handover(session: Session, line_code: str, day: dt.date) -> list[str]:
    """引き継ぎの確認の確認用: 出し直しで古くなった計画(実績を入れる前提)と、出し直し後の計画を入れる。

    古い計画は plans.is_stale と replacement_kitting_no を持つ(実際は既存アプリのビュー v_plan_stale から同期で入る)。
    """
    line = normalize_mounting_line(line_code)
    issue = day - dt.timedelta(days=7)
    old = _DemoPlan("1100", 1, 21, "DEMO-H1", "出し直し基板H", 100, 30.0, "09:00", "12:00")
    new = _DemoPlan("1100", 1, 22, "DEMO-H1", "出し直し基板H", 100, 30.0, "09:00", "12:00")
    with write_transaction(session):
        register_lines(session, [line])
        session.flush()
        old_kno, new_kno = (_upsert_plan(session, p, line, day, issue, "") for p in (old, new))
        row = session.get(Plan, (old_kno, old.lot_no))
        row.is_stale, row.replacement_kitting_no, row.replacement_count = True, new_kno, 1
        # 移す先の候補が無い、古い計画(手で選ぶ・「移さない」の確認用)と、手で選べる有効な計画
        lone = _DemoPlan("1101", 1, 23, "DEMO-H2", "候補なし基板I", 80, 30.0, "13:00", "15:00")
        other = _DemoPlan("1102", 1, 24, "DEMO-H3", "手で選ぶ基板J", 80, 30.0, "13:00", "15:00")
        lone_kno, other_kno = (_upsert_plan(session, p, line, day, issue, "") for p in (lone, other))
        session.get(Plan, (lone_kno, lone.lot_no)).is_stale = True
        _upsert_teitori(session, line)
        session.commit()
    return [old_kno, new_kno]


def seed_side_pair(session: Session, day: dt.date, side1_line: str = "S", side2_line: str = "U") -> list[str]:
    """面1と面2の紐づけ(現場の画面)の確認用: 1回目 Sライン、2回目 Uライン、同じロットNo.・同じファイルNo.の組。

    ラインが違うのでキー H ではつながらない(ロットNo.に --lot-suffix は使わない)。2回目の画面では、同じロットNo.・ファイルNo.の
    1回目がちょうど1つなので、候補として欄に入る。
    """
    issue = day - dt.timedelta(days=7)
    first = _DemoPlan("1200", 1, 31, "DEMO-L1", "紐づけ基板L", 100, 30.0, "09:00", "11:00")
    second = _DemoPlan("1200", 2, 32, "DEMO-L1", "紐づけ基板L", 100, 40.0, "11:30", "13:30")
    with write_transaction(session):
        register_lines(session, [side1_line, side2_line])
        session.flush()
        knos = [_upsert_plan(session, first, normalize_mounting_line(side1_line), day, issue, ""),
                _upsert_plan(session, second, normalize_mounting_line(side2_line), day, issue, "")]
        _upsert_teitori(session, normalize_mounting_line(side1_line))
        _upsert_teitori(session, normalize_mounting_line(side2_line))
        session.commit()
    return knos


def seed_record_samples(session: Session, day: dt.date, line_code: str = "R") -> list[str]:
    """生産記録票(印刷)の確認用: 10ロットと3ロットの両面の組(キッティングNo.でつながる)、片面だけの計画、面1とつながらない面2。

    数量は、この計画での生産数 100、これまでの累計 200、発注数 300(ロットごと)。記録は画面かAPIで入れる。
    """
    line = normalize_mounting_line(line_code)
    issue = day - dt.timedelta(days=7)
    plans = [_DemoPlan("1300", run, 41, f"DEMO-R{i:02d}", "10ロット基板M", 100, 30.0, "08:00", "09:00") for run in (1, 2) for i in range(1, 11)]
    plans += [_DemoPlan("1303", run, 47, f"DEMO-R{i}", "3ロット基板Q", 100, 30.0, "08:00", "09:00") for run in (1, 2) for i in (40, 41, 42)]
    plans.append(_DemoPlan("1301", 1, 43, "DEMO-R20", "片面基板N", 100, 30.0, "08:00", "09:00"))
    plans.append(_DemoPlan("1302", 2, 45, "DEMO-R30", "面2だけ基板P", 100, 30.0, "08:00", "09:00"))
    with write_transaction(session):
        register_lines(session, [line])
        session.flush()
        knos = [_upsert_plan(session, p, line, day, issue, "") for p in plans]
        for p, kno in zip(plans, knos, strict=True):
            row = session.get(Plan, (kno, p.lot_no))
            row.cumulative_qty, row.order_qty = 200, 300
        _upsert_teitori(session, line)
        session.commit()
    return list(dict.fromkeys(knos))


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


def seed_old_unstarted(session: Session, line_code: str, day: dt.date) -> list[str]:
    """遅れた未着手の計画の警告の確認用: 確認用の計画に加え、10日前に終わった未着手の計画(表示範囲を広げても入らない)を入れる。

    本アプリを使い始めた時刻(一番古い記録)より後に終わる必要があるので、`--stale-open` を入れたラインを同じDBに用意しておく。
    """
    knos = seed_demo(session, line_code, day)
    line = normalize_mounting_line(line_code)
    old = _DemoPlan("1200", 1, 25, "DEMO-OLD", "古い未着手基板K", 60, 30.0, "09:00", "12:00", -10)
    with write_transaction(session):
        knos.append(_upsert_plan(session, old, line, day, day - dt.timedelta(days=7), ""))
        session.commit()
    return knos


def seed_stale_open(session: Session, line_code: str, day: dt.date) -> list[int]:
    """「終了していない古い記録」の確認用: 確認用の計画を入れ、10日前に始めて終了していない段取りと生産を入れる(表示範囲を広げても入らない)。

    入れた工程の記録のIDを返す(管理画面で終了の時刻を入れる・取り消す確認用。e2e/zz-open-runs.spec.ts)。
    """
    knos = list(dict.fromkeys(seed_demo(session, line_code, day)))
    started_by = session.scalars(select(Operator).where(Operator.worker_key == worker_key("Y001"))).one().id
    start = dt.datetime.combine(day - dt.timedelta(days=10), dt.time(10, 0), tzinfo=clock.JST)
    ids = []
    with write_transaction(session):
        for kno, step in ((knos[0], "setup"), (knos[3], "production")):
            e = RunEvent(kitting_no=kno, step_type=step, seq=1, start_at=start, started_by=started_by,
                         start_request_id=f"demo-stale-{kno}-{step}", created_at=start)
            session.add(e)
            session.flush()
            ids.append(e.id)
        session.commit()
    return ids
