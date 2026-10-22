"""現場の画面からの実績の訂正のAPI(工程の記録と付帯作業)と、訂正の履歴。ルールは services/run_corrections.py など。

現場の画面から直せるのは、config.toml の [corrections] の範囲の記録だけ。管理画面からの訂正は別のAPIで作る。
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import CORRECTION_META, LineEventCorrectIn, RunEventAddIn, RunEventCorrectIn, VoidIn, _Recorder
from app.core.config import get_config
from app.db.session import get_session
from app.services import correction_history, line_event_corrections, masters, run_corrections
from app.services.correction_rules import FieldScope
from app.services.views import CorrectionOut, LineEventCorrectionResultOut, RunCorrectionResultOut

router = APIRouter(prefix="/api", tags=["corrections"])


def _field_scope() -> FieldScope:
    cfg = get_config()
    return FieldScope(cfg.schedule.day_start, cfg.corrections.field_margin_hours)


def _recorder(session: Session, body: _Recorder) -> int | None:
    return masters.resolve_operator_ref(session, body.operator_id, body.worker_id)


def _fields(body: RunEventCorrectIn | LineEventCorrectIn) -> dict:
    """送られた項目のうち、直す項目だけ(送らなかった項目は直さない)。"""
    return {k: getattr(body, k) for k in body.model_fields_set - CORRECTION_META}


@router.patch("/runs/{kitting_no}/events/{event_id}", response_model=RunCorrectionResultOut)
def correct_run_event(kitting_no: str, event_id: int, body: RunEventCorrectIn,
                      session: Session = Depends(get_session)) -> RunCorrectionResultOut:
    """工程の記録の開始・終了の時刻と、生産の区切りの生産数を直す(理由が必須)。"""
    return run_corrections.correct_run_event(
        session, kitting_no, event_id, _fields(body), body.reason, body.note, body.request_id, _field_scope(),
        operator_id=_recorder(session, body),
    )


@router.post("/runs/{kitting_no}/events/{event_id}/void", response_model=RunCorrectionResultOut)
def void_run_event(kitting_no: str, event_id: int, body: VoidIn,
                   session: Session = Depends(get_session)) -> RunCorrectionResultOut:
    """工程の記録を取り消す(記録は消さない。生産数・進捗・完了・タイムテーブルの計算から外す)。"""
    return run_corrections.void_run_event(
        session, kitting_no, event_id, body.reason, body.note, body.request_id, _field_scope(),
        operator_id=_recorder(session, body),
    )


@router.post("/runs/{kitting_no}/events", response_model=RunCorrectionResultOut)
def add_run_event(kitting_no: str, body: RunEventAddIn, session: Session = Depends(get_session)) -> RunCorrectionResultOut:
    """押し忘れた工程を後から記録する(後から足した印が付く)。"""
    return run_corrections.add_run_event(
        session, kitting_no, body.step_type, body.start_at, body.end_at, body.produced_qty, body.reason, body.note,
        body.request_id, _field_scope(), operator_id=_recorder(session, body),
    )


@router.get("/runs/{kitting_no}/corrections", response_model=list[CorrectionOut])
def kitting_corrections(kitting_no: str, session: Session = Depends(get_session)) -> list[CorrectionOut]:
    """計画のまとまりの工程の記録の訂正の履歴(新しい順)。"""
    return correction_history.kitting_corrections(session, kitting_no)


@router.patch("/lines/{line_code}/events/{event_id}", response_model=LineEventCorrectionResultOut)
def correct_line_event(line_code: str, event_id: int, body: LineEventCorrectIn,
                       session: Session = Depends(get_session)) -> LineEventCorrectionResultOut:
    """付帯作業の開始・終了の時刻と、理由(設備・記入)を直す(訂正の理由が必須)。"""
    return line_event_corrections.correct_line_event(
        session, line_code, event_id, _fields(body), body.reason, body.note, body.request_id, _field_scope(),
        operator_id=_recorder(session, body),
    )


@router.post("/lines/{line_code}/events/{event_id}/void", response_model=LineEventCorrectionResultOut)
def void_line_event(line_code: str, event_id: int, body: VoidIn,
                    session: Session = Depends(get_session)) -> LineEventCorrectionResultOut:
    """付帯作業を取り消す(記録は消さない)。"""
    return line_event_corrections.void_line_event(
        session, line_code, event_id, body.reason, body.note, body.request_id, _field_scope(),
        operator_id=_recorder(session, body),
    )


@router.get("/lines/{line_code}/corrections", response_model=list[CorrectionOut])
def line_event_corrections_of_day(
    line_code: str,
    date: dt.date | None = Query(default=None, description="稼働日(YYYY-MM-DD)。省略すると今の稼働日"),
    session: Session = Depends(get_session),
) -> list[CorrectionOut]:
    """付帯作業の訂正の履歴(付帯作業の開始がその稼働日にあるもの。新しい順)。"""
    return correction_history.line_event_corrections(session, line_code, date, get_config().schedule.day_start)
