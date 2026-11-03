"""生産記録票(A4縦、日本語とベトナム語の併記)に印刷する値を組み立てる。DBは読むだけ。

1枚 = 両面の1組。実績の訂正と取り消しの印を反映した今の値を出す(訂正は記録を直接書き換え、取り消した記録は除く)。
欄と元データ、付帯作業の範囲: docs/design/production-record.md
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_config
from app.db.models import Equipment, LineEvent, Reason, RunEvent
from app.domain.steps import StepType
from app.services.actuals_rows import lot_actuals
from app.services.completions import latest_completion, produced_total
from app.services.errors import NotFound, RuleViolation
from app.services.kitting_plans import KittingGroup, load_group
from app.services.production_record_pair import RecordPair, pair_of
from app.services.views import operator_name


class StepRowOut(BaseModel):
    date: str  # 記録の日付(M/D)
    worker: str
    start: str  # HH:MM
    end: str | None  # 終了していなければ空
    good_qty: int | None = None  # 生産の区切りの良品の台数(生産の行だけ。終了していなければ空)


class TroubleOut(BaseModel):
    name: str  # 種類と、設備や理由の文
    start: str
    end: str | None


class FaceOut(BaseModel):
    kitting_no: str
    line_code: str
    completed: bool
    setup: list[StepRowOut]
    n1_check: list[StepRowOut]
    production: list[StepRowOut]
    xray: list[StepRowOut]
    cleanup: list[StepRowOut]
    first_article: list[StepRowOut]  # 日付と作業者名だけ使う(終了していなければ end は空)
    good_total: int  # 良品の累計
    troubles: list[TroubleOut]


class LotRowOut(BaseModel):
    lot_no: str
    produced: int | None  # A: この計画での生産数(計画の数量)
    cumulative: int | None  # B: この計画を含めた生産累計数
    ordered: int | None  # C: ロットの全発注数
    actual: int | None = None  # Aの面の計画が完了しているときの、ロットの実績の台数(書き出しと同じ割り振り)。完了していなければ空


class HeaderOut(BaseModel):
    approver: str
    checker: str
    author: str
    revision_date: str
    version: str


class RecordSheetOut(BaseModel):
    header: HeaderOut
    file_no: str
    product_name: str
    lots: list[LotRowOut]
    qty_differs: list[str]  # 面1と面2でA・Bの値が違うロット(出すのは面1の値)
    side1: FaceOut | None
    side2: FaceOut | None
    side2_unlinked: bool  # 面1とつながっていない面2(印刷の上に「1回目と紐づける」を出す)
    side2_kitting_no: str | None


def _hm(t: dt.datetime) -> str:
    return t.strftime("%H:%M")


def _row(session: Session, e: RunEvent) -> StepRowOut:
    return StepRowOut(date=f"{e.start_at.month}/{e.start_at.day}", worker=operator_name(session, e.started_by) or "",
                      start=_hm(e.start_at), end=_hm(e.end_at) if e.end_at else None,
                      good_qty=e.produced_qty if e.step_type == StepType.PRODUCTION.value and e.end_at else None)


def _trouble_name(session: Session, e: LineEvent) -> str:
    reason, equipment = session.get(Reason, e.reason_id), session.get(Equipment, e.equipment_id) if e.equipment_id else None
    return " / ".join(x for x in (reason.name if reason else "", equipment.name if equipment else "", e.reason_text or "") if x)


def _troubles(session: Session, group: KittingGroup, events: list[RunEvent], now: dt.datetime) -> list[TroubleOut]:
    """その面の最初の工程の開始から片付けの終了までに、その面のラインで起きた付帯作業(終了していなければ今まで)。"""
    if not events:
        return []
    start = min(e.start_at for e in events)
    cleanups = [e.end_at for e in events if e.step_type == StepType.CLEANUP.value and e.end_at]
    end = max(cleanups) if cleanups else max([now] + [e.end_at for e in events if e.end_at])
    rows = session.scalars(select(LineEvent).where(
        LineEvent.line_code == group.line_code, LineEvent.voided_at.is_(None), LineEvent.start_at < end,
        or_(LineEvent.end_at.is_(None), LineEvent.end_at > start)).order_by(LineEvent.start_at, LineEvent.id))
    return [TroubleOut(name=_trouble_name(session, e), start=_hm(e.start_at), end=_hm(e.end_at) if e.end_at else None) for e in rows]


def face_out(session: Session, group: KittingGroup, now: dt.datetime) -> FaceOut:
    events = list(session.scalars(select(RunEvent).where(RunEvent.kitting_no == group.kitting_no, RunEvent.voided_at.is_(None))
                                  .order_by(RunEvent.start_at, RunEvent.id)))
    by = lambda step: [_row(session, e) for e in events if e.step_type == step.value]  # noqa: E731
    return FaceOut(
        kitting_no=group.kitting_no, line_code=group.line_code, completed=latest_completion(session, group.kitting_no) is not None,
        setup=by(StepType.SETUP), n1_check=by(StepType.N1_CHECK), production=by(StepType.PRODUCTION), xray=by(StepType.XRAY),
        cleanup=by(StepType.CLEANUP), first_article=by(StepType.FIRST_ARTICLE), good_total=produced_total(session, group.kitting_no),
        troubles=_troubles(session, group, events, now),
    )


def _actuals(session: Session, pair: RecordPair, faces: dict[str, FaceOut]) -> dict[str, int]:
    """ロットNo. → 実績の台数。両面の組は面2の行の値、面2が無いロットは面1の値(書き出しと同じ)。"""
    day_start = get_config().schedule.day_start
    result: dict[str, int] = {}
    for g in (pair.side1, pair.side2):  # 面2が後に入って、面1の値を上書きする
        if g is not None and faces[g.kitting_no].completed:
            result.update(lot_actuals(session, g, day_start))
    return result


def _lots(pair: RecordPair, actuals: dict[str, int], faces_done: dict[str, bool]) -> tuple[list[LotRowOut], list[str]]:
    """ロットNo.ごとに1行。数量は面1の計画の値(面1にそのロットが無ければ面2)。面1と面2で違うロットも返す。"""
    s1 = {lot.lot_no: lot for lot in (pair.side1.lots if pair.side1 else [])}
    s2 = {lot.lot_no: lot for lot in (pair.side2.lots if pair.side2 else [])}
    rows, differs = [], []
    for no in sorted(s1.keys() | s2.keys()):
        lot = s1.get(no) or s2[no]
        a_face = (pair.side1 if no in s1 else pair.side2).kitting_no  # type: ignore[union-attr]
        rows.append(LotRowOut(lot_no=no, produced=lot.planned_qty, cumulative=lot.cumulative_qty, ordered=lot.order_qty,
                              actual=actuals.get(no) if faces_done.get(a_face) else None))
        other = s2.get(no) if no in s1 else None
        if other is not None and (other.planned_qty, other.cumulative_qty) != (lot.planned_qty, lot.cumulative_qty):
            differs.append(no)
    return rows, differs


def build_sheet(session: Session, kitting_no: str) -> RecordSheetOut:
    """キッティングNo.(どちらの面でもよい)の組の生産記録票。取り消された計画は NotFound、どちらの面も完了していなければ 409。"""
    group = load_group(session, kitting_no)
    if group.status != "active":
        raise NotFound(f"計画(キッティングNo. {kitting_no})は取り消されています")
    pair = pair_of(session, group)
    now = clock.now()
    faces = {g.kitting_no: face_out(session, g, now) for g in pair.faces()}
    if not any(f.completed for f in faces.values()):
        raise RuleViolation("片付けが終わった計画だけ、生産記録票を印刷できます")
    lots, differs = _lots(pair, _actuals(session, pair, faces), {k: f.completed for k, f in faces.items()})
    first = (pair.side1 or pair.side2)  # type: ignore[assignment]
    cfg = get_config().production_record
    return RecordSheetOut(
        header=HeaderOut(approver=cfg.approver, checker=cfg.checker, author=cfg.author, revision_date=cfg.revision_date, version=cfg.version),
        file_no=first.file_no, product_name=first.product_name, lots=lots, qty_differs=differs,
        side1=faces[pair.side1.kitting_no] if pair.side1 else None, side2=faces[pair.side2.kitting_no] if pair.side2 else None,
        side2_unlinked=pair.unlinked_side2, side2_kitting_no=pair.side2.kitting_no if pair.side2 else None,
    )
