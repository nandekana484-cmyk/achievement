"""集計のもとになる「時間の区間」(CSV と日報で使う)。DBは読むだけ。

1件 = 取り消していない工程の記録、または付帯作業の記録を、稼働日ごとに分けたもの。終了していない記録は今までで計算する。
詳細: docs/design/reports.md
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import Equipment, LineEvent, Reason, RunCorrection, RunEvent
from app.domain.intervals import minutes_between, split_by_workday
from app.domain.steps import StepType
from app.domain.workday import workday_range
from app.services.kitting_plans import KittingGroup, load_group
from app.services.views import operator_name, worker_id_of

KIND_STEP = "step"  # 工程
KIND_LINE_EVENT = "line_event"  # 付帯作業


class IntervalOut(BaseModel):
    workday: dt.date
    line_code: str
    kind: str  # step / line_event
    event_id: int
    kitting_no: str | None
    lot_nos: str  # 複数は「、」でつなげる
    file_no: str | None
    product_names: str
    run_no: int | None
    step_type: str | None  # 工程のとき
    what: str  # 工程の名前、または付帯作業の理由の名前
    restart_reason: str | None  # 生産の再開理由
    equipment: str | None
    reason_text: str | None  # 付帯作業の理由の記入
    original_start: dt.datetime
    original_end: dt.datetime | None  # 終了していなければ空
    start: dt.datetime  # その稼働日に割り当てた開始・終了
    end: dt.datetime | None
    minutes: float  # 終了していなければ、出力した時刻まで
    produced_qty: int | None  # 生産の区切りのみ。稼働日で分けたときは、終了を含む区間に付ける
    started_by: str
    ended_by: str | None
    added_later: bool
    corrected: bool
    open: bool  # 作業中(終了していない)


def _person(session: Session, operator_id: int | None) -> str | None:
    name = operator_name(session, operator_id)
    if name is None:
        return None
    wid = worker_id_of(session, operator_id)
    return f"{name}({wid})" if wid else name


def _name(session: Session, model: type, row_id: int | None) -> str | None:
    row = session.get(model, row_id) if row_id is not None else None
    return row.name if row is not None else None


def _corrected_ids(session: Session, table: str, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return set(session.scalars(select(RunCorrection.target_id).where(
        RunCorrection.target_table == table, RunCorrection.target_id.in_(ids))))


def _overlapping(model: type, start: dt.datetime, end: dt.datetime):  # noqa: ANN202
    return [model.voided_at.is_(None), model.start_at < end, or_(model.end_at.is_(None), model.end_at > start)]


def _pieces(base: dict, start: dt.datetime, end: dt.datetime | None, now: dt.datetime, day_start: dt.time,
            days: tuple[dt.date, dt.date], qty: int | None) -> list[IntervalOut]:
    """記録1件を稼働日ごとの区間にする(期間の外の稼働日は捨てる)。"""
    pieces = split_by_workday(start, end or max(now, start), day_start)
    out = []
    for i, (day, s, e) in enumerate(pieces):
        if not days[0] <= day <= days[1]:
            continue
        last = i == len(pieces) - 1
        out.append(IntervalOut(
            **base, workday=day, original_start=start, original_end=end, start=s, end=e if end is not None or not last else None,
            minutes=minutes_between(s, e), produced_qty=qty if last else None, open=end is None,
        ))
    return out


def _step_intervals(session: Session, line_code: str | None, start: dt.datetime, end: dt.datetime, now: dt.datetime,
                    day_start: dt.time, days: tuple[dt.date, dt.date]) -> list[IntervalOut]:
    events = list(session.scalars(select(RunEvent).where(*_overlapping(RunEvent, start, end))))
    corrected = _corrected_ids(session, RunEvent.__tablename__, [e.id for e in events])
    groups: dict[str, KittingGroup] = {}
    out = []
    for e in events:
        g = groups.get(e.kitting_no) or groups.setdefault(e.kitting_no, load_group(session, e.kitting_no))
        if line_code is not None and g.line_code != line_code:
            continue
        base = dict(
            line_code=g.line_code, kind=KIND_STEP, event_id=e.id, kitting_no=e.kitting_no,
            lot_nos="、".join(lot.lot_no for lot in g.lots),
            product_names="、".join(dict.fromkeys(lot.product_name for lot in g.lots)),
            file_no=g.file_no, run_no=g.run_no, step_type=e.step_type, what=StepType(e.step_type).label,
            restart_reason=_name(session, Reason, e.restart_reason_id), equipment=_name(session, Equipment, e.equipment_id),
            reason_text=None, started_by=_person(session, e.started_by) or "", ended_by=_person(session, e.ended_by),
            added_later=bool(e.added_later), corrected=e.id in corrected,
        )
        out += _pieces(base, e.start_at, e.end_at, now, day_start, days, e.produced_qty)
    return out


def _line_event_intervals(session: Session, line_code: str | None, start: dt.datetime, end: dt.datetime, now: dt.datetime,
                          day_start: dt.time, days: tuple[dt.date, dt.date]) -> list[IntervalOut]:
    conds = _overlapping(LineEvent, start, end) + ([LineEvent.line_code == line_code] if line_code is not None else [])
    events = list(session.scalars(select(LineEvent).where(*conds)))
    corrected = _corrected_ids(session, LineEvent.__tablename__, [e.id for e in events])
    out = []
    for e in events:
        base = dict(
            line_code=e.line_code, kind=KIND_LINE_EVENT, event_id=e.id, kitting_no=None, lot_nos="", product_names="",
            file_no=None, run_no=None, step_type=None, what=_name(session, Reason, e.reason_id) or "", restart_reason=None,
            equipment=_name(session, Equipment, e.equipment_id), reason_text=e.reason_text,
            started_by=_person(session, e.started_by) or "", ended_by=_person(session, e.ended_by),
            added_later=False, corrected=e.id in corrected,
        )
        out += _pieces(base, e.start_at, e.end_at, now, day_start, days, None)
    return out


def build_intervals(session: Session, day_from: dt.date, day_to: dt.date, line_code: str | None,
                    day_start: dt.time) -> list[IntervalOut]:
    """稼働日 day_from〜day_to(両端を含む)の区間。line_code が None ならすべてのライン。稼働日・ライン・開始の順。"""
    start, end = workday_range(day_from, day_start)[0], workday_range(day_to, day_start)[1]
    now = clock.now()
    days = (day_from, day_to)
    rows = (_step_intervals(session, line_code, start, end, now, day_start, days)
            + _line_event_intervals(session, line_code, start, end, now, day_start, days))
    return sorted(rows, key=lambda r: (r.workday, r.line_code, r.start, r.kind, r.event_id))
