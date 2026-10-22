"""ライン画面用の取得(開発指針 7.1)。計画はキッティングNo.のまとまりの単位。DBは読むだけ。

詳細: docs/design/line-screen.md
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import LineEvent, RunEvent
from app.domain.workday import display_range, workday_of, workday_range
from app.services.kitting_plans import KittingGroup, load_active_groups, load_group
from app.services.line_operators import current_row
from app.services.masters import get_line
from app.services.ng_inputs import latest_ng, ng_choices
from app.services.plan_query import board_kitting_nos, kitting_nos_overlapping
from app.services.plan_views import BoardOut, BoardPlanOut, kitting_plan_out
from app.services.completions import latest_completion, produced_total
from app.services.views import current_operator_out, line_event_out, run_completion_out, run_event_out


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def board_plan_out(session: Session, g: KittingGroup) -> BoardPlanOut:
    """まとまり1件の、工程の記録・生産数の合計・NG数・最新の完了・計画の進捗率。"""
    events = session.scalars(select(RunEvent).where(RunEvent.kitting_no == g.kitting_no).order_by(RunEvent.start_at, RunEvent.id))
    produced = produced_total(session, g.kitting_no)
    completion = latest_completion(session, g.kitting_no)
    return BoardPlanOut(
        plan=kitting_plan_out(g),
        events=[run_event_out(session, e) for e in events],
        produced_qty=produced,
        ng_entries=latest_ng(session, g.kitting_no),
        ng_choices=ng_choices(session, g),
        completed=completion is not None,
        completion=run_completion_out(completion) if completion is not None else None,
        progress=_ratio(produced, g.planned_qty),
    )


def get_run(session: Session, kitting_no: str) -> BoardPlanOut:
    """まとまり1件の状態(表示範囲の外の計画を、検索して選んだときに使う)。"""
    return board_plan_out(session, load_group(session, kitting_no))


def get_board(session: Session, line_code: str, day: dt.date | None, day_start: dt.time) -> BoardOut:
    """稼働日(省略すると今の稼働日)のライン画面の情報。"""
    line = get_line(session, line_code)
    now = clock.now()
    day = day or workday_of(now, day_start)
    work_start, work_end = workday_range(day, day_start)
    disp_start, disp_end = display_range(day, day_start)

    groups = load_active_groups(session, board_kitting_nos(session, line.line_code, disp_start, disp_end, now))
    operator = current_row(session, line.line_code)
    return BoardOut(
        line_code=line.line_code, date=day,
        workday_start=work_start, workday_end=work_end, display_start=disp_start, display_end=disp_end, server_time=now,
        current_operator=current_operator_out(session, operator) if operator is not None else None,
        plans=[board_plan_out(session, g) for g in groups],
        line_events=[line_event_out(session, e) for e in _line_events(session, line.line_code, disp_start, disp_end, now)],
        line_progress=_line_progress(session, line.line_code, work_start, work_end),
        # TODO(要確認): 稼働率の定義
        utilization=None,
    )


def _line_events(session: Session, line_code: str, start: dt.datetime, end: dt.datetime, now: dt.datetime) -> list[LineEvent]:
    """表示範囲に重なる付帯作業。終了していないものは今まで続いているとみなす。"""
    still_open = LineEvent.end_at.is_(None) if now >= start else false()  # 取り消した記録も返す(画面の履歴に出す)
    return list(session.scalars(
        select(LineEvent).where(
            LineEvent.line_code == line_code, LineEvent.start_at < end, or_(still_open, LineEvent.end_at > start),
        ).order_by(LineEvent.start_at, LineEvent.id)
    ))


def _line_progress(session: Session, line_code: str, work_start: dt.datetime, work_end: dt.datetime) -> float | None:
    """ラインの進捗率。画面に出さない計画(未着手で過ぎたもの)も含めて、稼働日に重なるまとまりで計算する。

    TODO(要確認): ラインの進捗率の定義(今は 稼働日に重なる計画の生産数の合計 ÷ 計画数の合計)
    """
    groups = load_active_groups(session, kitting_nos_overlapping(session, line_code, work_start, work_end))
    produced = sum(produced_total(session, g.kitting_no) for g in groups)
    return _ratio(produced, sum(g.planned_qty for g in groups))
