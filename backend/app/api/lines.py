"""ライン単位のAPI(今の担当者・付帯作業・ライン画面用の取得)とマスタの取得。"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import ChangeOperatorIn, LineEventEndIn, LineEventStartIn
from app.core.config import get_config
from app.db.session import get_session
from app.services import board, line_events, line_operators, masters
from app.services.plan_views import BoardOut
from app.services.views import CurrentOperatorOut, LineEventOut, MastersOut, OperatorOut

router = APIRouter(prefix="/api", tags=["lines"])


@router.get("/lines/{line_code}/operator", response_model=CurrentOperatorOut | None)
def get_operator(line_code: str, session: Session = Depends(get_session)) -> CurrentOperatorOut | None:
    """ラインの今の担当者(未設定なら null)。"""
    return line_operators.get_current_operator(session, line_code)


@router.put("/lines/{line_code}/operator", response_model=CurrentOperatorOut)
def change_operator(line_code: str, body: ChangeOperatorIn, session: Session = Depends(get_session)) -> CurrentOperatorOut:
    """ラインの今の担当者を交代する(operator_id か worker_id のどちらかで指定)。"""
    operator_id = masters.resolve_operator_ref(session, body.operator_id, body.worker_id)
    return line_operators.change_operator(session, line_code, operator_id, body.request_id)


@router.get("/operators/lookup", response_model=OperatorOut)
def lookup_operator(
    worker_id: str = Query(max_length=64, description="作業者ID(全角・半角、大文字・小文字は区別しない)"),
    session: Session = Depends(get_session),
) -> OperatorOut:
    """作業者IDで、有効な作業者を呼び出す(無ければ 404「作業者IDが見つかりません」)。"""
    return OperatorOut.model_validate(masters.lookup_operator(session, worker_id))


@router.post("/lines/{line_code}/events/start", response_model=LineEventOut)
def start_line_event(line_code: str, body: LineEventStartIn, session: Session = Depends(get_session)) -> LineEventOut:
    """付帯作業を開始する。"""
    return line_events.start_line_event(
        session, line_code, body.reason_id, body.request_id, equipment_id=body.equipment_id, reason_text=body.reason_text,
        operator_id=masters.resolve_operator_ref(session, body.operator_id, body.worker_id),
    )


@router.post("/lines/{line_code}/events/{event_id}/end", response_model=LineEventOut)
def end_line_event(line_code: str, event_id: int, body: LineEventEndIn, session: Session = Depends(get_session)) -> LineEventOut:
    """付帯作業を終了する。"""
    return line_events.end_line_event(session, line_code, event_id, body.request_id,
                                      operator_id=masters.resolve_operator_ref(session, body.operator_id, body.worker_id))


@router.get("/lines/{line_code}/board", response_model=BoardOut)
def get_board(
    line_code: str,
    date: dt.date | None = Query(default=None, description="稼働日(YYYY-MM-DD)。省略すると今の稼働日"),
    session: Session = Depends(get_session),
) -> BoardOut:
    """ライン画面用: 表示範囲の計画ごとの工程の記録・生産数・NG数・完了・進捗率と、付帯作業、今の担当者。"""
    return board.get_board(session, line_code, date, get_config().schedule.day_start)


@router.get("/masters", response_model=MastersOut)
def get_masters(
    line_code: str | None = Query(default=None, description="指定すると、設備はそのラインのものだけ"),
    session: Session = Depends(get_session),
) -> MastersOut:
    """有効なマスタ(ライン・作業者・設備・理由)を sort_order 順に返す。"""
    return masters.list_masters(session, line_code)
