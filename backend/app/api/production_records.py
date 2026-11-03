"""生産記録票の印刷用のAPI(現場の画面。読み取りだけ)。認証は現場の画面と同じ(IP制限)。詳細: docs/design/production-record.md"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.production_record import RecordSheetOut, build_sheet
from app.services.production_record_list import RecordRowOut, list_records

router = APIRouter(prefix="/api/production-records", tags=["production-records"])


@router.get("", response_model=list[RecordRowOut])
def list_production_records(
    line: str | None = Query(default=None, description="ライン記号(どちらかの面のライン)"),
    kitting_no: str | None = Query(default=None, description="キッティングNo.(部分一致)"),
    lot_no: str | None = Query(default=None, description="ロットNo.(部分一致)"),
    session: Session = Depends(get_session),
) -> list[RecordRowOut]:
    """印刷できる組(どちらかの面の完了日が過去31日以内)を、完了日の新しい順に返す。"""
    return list_records(session, line or None, kitting_no or None, lot_no or None)


@router.get("/{kitting_no}", response_model=RecordSheetOut)
def get_production_record(kitting_no: str, session: Session = Depends(get_session)) -> RecordSheetOut:
    """キッティングNo.(どちらの面でもよい)の組の、生産記録票に印刷する値。"""
    return build_sheet(session, kitting_no)
