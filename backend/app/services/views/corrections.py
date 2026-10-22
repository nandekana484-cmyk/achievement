"""実績の訂正の履歴と、訂正の結果の応答の形。"""

from __future__ import annotations

import datetime as dt
import json

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import Equipment, LineEvent, Reason, RunCorrection, RunEvent
from app.domain.corrections import CorrectionReason
from app.services.views.line_events import LineEventOut
from app.services.views.operators import operator_name, worker_id_of
from app.services.views.runs import RunCompletionOut, RunEventOut

Value = str | int | bool | None

# 名前を添える項目(マスタの番号)
_NAMED_FIELDS = {"reason_id": Reason, "equipment_id": Equipment}


class CorrectionChangeOut(BaseModel):
    field: str  # start_at / end_at / produced_qty / reason_id / equipment_id / reason_text / voided_at など
    before: Value
    after: Value
    before_name: str | None = None  # reason_id・equipment_id のときのマスタの名前
    after_name: str | None = None
    before_name_vi: str | None = None
    after_name_vi: str | None = None


class CorrectionOut(BaseModel):
    id: int
    target_table: str  # run_events / line_events
    target_id: int
    kitting_no: str | None
    line_code: str
    kind: str  # update(変更)/ void(取り消し)/ add(後からの追加)
    changes: list[CorrectionChangeOut]
    reason: str  # mistake / forgot / wrong_qty / other
    reason_label: str  # 理由の日本語の名前
    note: str | None
    corrected_by: int
    corrected_by_name: str
    corrected_by_worker_id: str | None
    corrected_at: dt.datetime
    source: str  # field(現場)/ admin(管理)
    step_type: str | None  # 工程の記録のとき
    seq: int | None
    line_event_reason_name: str | None  # 付帯作業のとき(今の理由)
    line_event_reason_name_vi: str | None


class RunCorrectionResultOut(BaseModel):
    """工程の記録の訂正の結果。完了した計画なら、作り直した完了も返す。"""

    correction: CorrectionOut
    event: RunEventOut
    completed: bool  # 訂正のあと、完了しているか
    completion: RunCompletionOut | None  # この訂正で作り直した完了


class LineEventCorrectionResultOut(BaseModel):
    correction: CorrectionOut
    event: LineEventOut


def _change_out(session: Session, c: dict) -> CorrectionChangeOut:
    out = CorrectionChangeOut(field=c["field"], before=c.get("before"), after=c.get("after"))
    model = _NAMED_FIELDS.get(out.field)
    if model is not None:
        for side in ("before", "after"):
            value = getattr(out, side)
            row = session.get(model, value) if isinstance(value, int) else None
            if row is not None:
                setattr(out, f"{side}_name", row.name)
                setattr(out, f"{side}_name_vi", row.name_vi)
    return out


def correction_out(session: Session, c: RunCorrection) -> CorrectionOut:
    step_type = seq = reason_name = reason_name_vi = None
    if c.target_table == RunEvent.__tablename__:
        e = session.get(RunEvent, c.target_id)
        step_type, seq = (e.step_type, e.seq) if e is not None else (None, None)
    else:
        le = session.get(LineEvent, c.target_id)
        reason = session.get(Reason, le.reason_id) if le is not None else None
        reason_name, reason_name_vi = (reason.name, reason.name_vi) if reason is not None else (None, None)
    return CorrectionOut(
        id=c.id, target_table=c.target_table, target_id=c.target_id, kitting_no=c.kitting_no, line_code=c.line_code,
        kind=c.kind, changes=[_change_out(session, x) for x in json.loads(c.changes_json)],
        reason=c.reason, reason_label=CorrectionReason(c.reason).label, note=c.note,
        corrected_by=c.corrected_by, corrected_by_name=operator_name(session, c.corrected_by) or "",
        corrected_by_worker_id=worker_id_of(session, c.corrected_by), corrected_at=c.corrected_at, source=c.source,
        step_type=step_type, seq=seq, line_event_reason_name=reason_name, line_event_reason_name_vi=reason_name_vi,
    )
