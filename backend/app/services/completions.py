"""完了(開発指針 5.7)。片付けの終了 = その回の完了。訂正したら完了の写しを作り直す(最新の有効な行を正とする)。

有効な完了 = 完了にした片付けが取り消されていない行。詳細: docs/design/run-records.md
"""

from __future__ import annotations

import json

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.db.models import RunCompletion, RunEvent
from app.domain.corrections import CompletionKind
from app.domain.steps import StepType
from app.services.kitting_plans import KittingGroup, load_group
from app.services.ng_inputs import latest_ng
from app.services.plan_views import lot_out
from app.services.teitori_lookup import lookup_teitori
from app.services.views import LotOut


def produced_total(session: Session, kitting_no: str) -> int:
    """生産の区切りの生産数の合計(終了した区切りだけ。取り消した記録は除く)。"""
    return session.scalar(select(func.coalesce(func.sum(RunEvent.produced_qty), 0)).where(
        RunEvent.kitting_no == kitting_no, RunEvent.step_type == StepType.PRODUCTION.value,
        RunEvent.end_at.is_not(None), RunEvent.voided_at.is_(None),
    )) or 0


def valid_completion():  # noqa: ANN201
    """完了にした片付けが取り消されていない(SQL の条件。RunCompletion と組み合わせる)。"""
    return exists().where(RunEvent.id == RunCompletion.cleanup_event_id, RunEvent.voided_at.is_(None))


def latest_completion(session: Session, kitting_no: str) -> RunCompletion | None:
    """最新の有効な完了(作った順で最後のもの)。無ければ完了でない。"""
    return session.scalars(select(RunCompletion).where(RunCompletion.kitting_no == kitting_no, valid_completion())
                           .order_by(RunCompletion.id.desc())).first()


def _latest_cleanup(session: Session, kitting_no: str) -> RunEvent | None:
    """終了した片付けのうち、取り消されていない最後のもの。"""
    return session.scalars(select(RunEvent).where(
        RunEvent.kitting_no == kitting_no, RunEvent.step_type == StepType.CLEANUP.value,
        RunEvent.end_at.is_not(None), RunEvent.voided_at.is_(None),
    ).order_by(RunEvent.end_at.desc(), RunEvent.id.desc())).first()


def create_completion(
    session: Session, group: KittingGroup, cleanup: RunEvent,
    kind: CompletionKind = CompletionKind.CLEANUP, correction_id: int | None = None, base: RunCompletion | None = None,
) -> RunCompletion:
    """完了の行を作る。生産数とNG数は今の値。計画数・想定タクト・丁取り数・ロットの一覧は base があればその写しを引き継ぐ。"""
    teitori, teitori_status = (base.teitori_snapshot, base.teitori_status_snapshot) if base and base.teitori_status_snapshot is not None         else lookup_teitori(session, group.first.file_no, group.first.line_code)
    c = RunCompletion(
        kitting_no=group.kitting_no, cleanup_event_id=cleanup.id, kind=kind.value, correction_id=correction_id,
        completed_at=cleanup.end_at, produced_qty=produced_total(session, group.kitting_no),
        plan_qty_snapshot=base.plan_qty_snapshot if base else group.planned_qty,
        takt_sec_snapshot=base.takt_sec_snapshot if base else group.takt_sec,
        lots_snapshot=base.lots_snapshot if base else _lots_json(group),
        ng_snapshot=json.dumps([n.model_dump(mode="json") for n in latest_ng(session, group.kitting_no)], ensure_ascii=False),
        teitori_snapshot=teitori, teitori_status_snapshot=teitori_status,  # 詳細: docs/design/metrics.md
    )
    session.add(c)
    session.flush()
    return c


def _lots_json(group: KittingGroup) -> str:
    lots: list[LotOut] = [lot_out(lot) for lot in group.lots]
    return json.dumps([lot.model_dump() for lot in lots], ensure_ascii=False)


def rebuild_after_correction(session: Session, kitting_no: str, correction_id: int) -> RunCompletion | None:
    """工程の記録を訂正したあと、完了の写しを作り直す。終了した片付けが残っていなければ完了でない(None)。

    計画を写した値は、それまでの有効な完了から引き継ぐ(訂正で計画の写しが今の計画に変わらないように)。
    """
    cleanup = _latest_cleanup(session, kitting_no)
    if cleanup is None:
        return None
    base = session.scalars(select(RunCompletion).where(RunCompletion.kitting_no == kitting_no)
                           .order_by(RunCompletion.id.desc())).first()
    return create_completion(session, load_group(session, kitting_no), cleanup, CompletionKind.CORRECTION, correction_id, base)
