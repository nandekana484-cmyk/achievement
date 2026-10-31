"""実績の書き出しの一覧(1行 = キッティングNo.+ロットNo.)。片付けが終わった計画だけ。DBは読むだけ。

- 面2の計画があるロットは、つながる面2の行にまとめる(面1の行は出さない)。面2が無いロットは面1の行を出す
- 面1と面2は、ロットNo. + キッティングNo.の回を除いた部分(キー H)か、人が確定したひも付けでつなぐ(services/side_links.py)。
  面2があるのにつながらない面1は、書き出しの対象から外し、「ひも付けの確認」に出す
- 生産数はキッティングNo.の累計(取り消した記録を除く)を、ロットに割り振る(domain/allocation.py)
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PLAN_CANCELLED, Operator, RunCompletion, RunEvent, RunNgInput
from app.domain.allocation import allocate
from app.domain.workday import workday_of, workday_range
from app.services.completions import latest_completion, produced_total, valid_completion
from app.services.kitting_plans import KittingGroup, load_group
from app.services.side_links import LinkCheckOut, link_checks, link_for_side1, side1_for_side2

W_CANCELLED = "取消の計画です(既存アプリに計画がありません)"
# 取消の理由ごとの文(plans.cancel_reason)。空は前のアプリで取り消したもの = 読めなくなった
W_CANCELLED_BY = {
    "vanished": W_CANCELLED,
    "reissued": "取消の計画です(出し直しで古くなりました。新しいキッティングNo.で出します)",
    "carried_over": "取消の計画です(実績は新しいキッティングNo.へ引き継ぎ済みです)",
}
W_NO_WORKER = "片付けを終えた人の作業者IDがありません"
W_NO_SOURCE = "元のDB(正とした月次DB)が分かりません"
W_PENDING = "面2の計画があるのに、キッティングNo.でつながりません。「ひも付けの確認」で面2の計画を選んでください"
W_UNLINKED = "「ひも付けの確認」で「つながない」にしたため、書き出しません"
N_NO_SIDE1 = "つながる面1の計画が無いため、NG面1は0です"


class ActualsRowOut(BaseModel):
    kitting_no: str
    lot_no: str
    file_no: str
    side: int  # 面(1 / 2)
    line_code: str
    product_name: str
    planned_qty: int
    produced_qty: int  # 割り振った生産数(累計)
    kitting_produced_total: int  # キッティングNo.の生産数の累計(割り振る前)
    kitting_hidden_qty: int  # 同じキッティングNo.で一覧に出さないロット(面2にまとめたもの)に割り振った数
    ng_side1: int
    ng_side2: int
    worker_id: str | None  # 片付けを終えた人
    operator_name: str | None
    completed_on: dt.date  # 完了日(片付けの終了の稼働日)
    source_db: str | None  # そのロットの正のDB(月次DBのフォルダ名)
    side1_kitting_no: str | None  # 面2の行で、ひも付けた面1の計画
    exportable: bool
    warnings: list[str]  # 書き出しの対象から外す理由
    notes: list[str]  # 書き出すが、確かめてほしいこと


class ActualsListOut(BaseModel):
    date_from: dt.date
    date_to: dt.date
    line_code: str | None
    rows: list[ActualsRowOut]
    link_checks: list[LinkCheckOut]  # ひも付けの確認(一覧のロットの、キッティングNo.でつながらない面1)
    pending_links: int  # そのうち未確定の数


@dataclass
class _Pairing:
    hidden: bool  # 面2の行にまとめるので出さない(面1の計画のロット)
    side1_kitting_no: str | None = None
    warning: str | None = None


def build_rows(session: Session, date_from: dt.date, date_to: dt.date, line_code: str | None,
               day_start: dt.time) -> ActualsListOut:
    """期間(完了日の稼働日)とラインで絞った、書き出しの一覧。"""
    start, _ = workday_range(date_from, day_start)
    _, end = workday_range(date_to, day_start)
    rows: list[ActualsRowOut] = []
    lots: set[tuple[str, str]] = set()
    for kno in _completed_kittings(session, start, end):
        completion = latest_completion(session, kno)
        if completion is None or not (start <= completion.completed_at < end):
            continue  # 最新の完了が期間の外(やり直した・取り消した)
        group = load_group(session, kno)
        if line_code and group.line_code != line_code:
            continue
        rows += _group_rows(session, group, completion, day_start)
        lots |= {(lot.lot_no, group.file_no) for lot in group.lots}
    rows.sort(key=lambda r: (r.completed_on, r.line_code, r.kitting_no, r.lot_no))
    checks = link_checks(session, lots)
    return ActualsListOut(date_from=date_from, date_to=date_to, line_code=line_code, rows=rows,
                          link_checks=checks, pending_links=sum(c.state == "pending" for c in checks))


def _completed_kittings(session: Session, start: dt.datetime, end: dt.datetime) -> list[str]:
    return sorted(set(session.scalars(select(RunCompletion.kitting_no).where(
        RunCompletion.completed_at >= start, RunCompletion.completed_at < end, valid_completion()))))


def _group_rows(session: Session, group: KittingGroup, completion: RunCompletion, day_start: dt.time) -> list[ActualsRowOut]:
    total = produced_total(session, group.kitting_no)
    qtys = allocate(total, [lot.planned_qty for lot in group.lots])
    pairings = [_pairing(session, group, lot.lot_no) for lot in group.lots]
    hidden_qty = sum(q for q, p in zip(qtys, pairings, strict=True) if p.hidden)
    worker_id, name = _cleanup_operator(session, completion)
    common = _common_warnings(group, worker_id)
    rows = []
    for lot, qty, p in zip(group.lots, qtys, pairings, strict=True):
        if p.hidden:
            continue
        warnings = [*common, *([p.warning] if p.warning else []), *([] if lot.source_db else [W_NO_SOURCE])]
        ng1, ng2, notes = _ng(session, group, lot.lot_no, p.side1_kitting_no)
        if group.run_no == 2 and not p.side1_kitting_no:
            notes.append(N_NO_SIDE1)
        if p.side1_kitting_no and latest_completion(session, p.side1_kitting_no) is None:
            notes.append(f"面1の計画({p.side1_kitting_no})は完了していません")
        rows.append(ActualsRowOut(
            kitting_no=group.kitting_no, lot_no=lot.lot_no, file_no=group.file_no, side=group.run_no,
            line_code=group.line_code, product_name=lot.product_name, planned_qty=lot.planned_qty, produced_qty=qty,
            kitting_produced_total=total, kitting_hidden_qty=hidden_qty, ng_side1=ng1, ng_side2=ng2,
            worker_id=worker_id, operator_name=name, completed_on=workday_of(completion.completed_at, day_start),
            source_db=lot.source_db, side1_kitting_no=p.side1_kitting_no, exportable=not warnings,
            warnings=warnings, notes=notes,
        ))
    return rows


def _common_warnings(group: KittingGroup, worker_id: str | None) -> list[str]:
    return [*([W_CANCELLED_BY.get(group.cancel_reason or 'vanished', W_CANCELLED)] if group.status == PLAN_CANCELLED else []), *([] if worker_id else [W_NO_WORKER])]


def _pairing(session: Session, group: KittingGroup, lot_no: str) -> _Pairing:
    """そのロットの行を出すか(面1の行は、つながる面2の行にまとめる)、面2の行ならどの面1の計画とつながるか。"""
    if group.run_no == 2:
        return _Pairing(hidden=False, side1_kitting_no=side1_for_side2(session, lot_no, group.file_no, group.kitting_no))
    link = link_for_side1(session, lot_no, group.file_no, group.kitting_no)
    if link.state in ("h", "confirmed"):
        return _Pairing(hidden=True)
    if link.state == "pending":
        return _Pairing(hidden=False, warning=W_PENDING)
    if link.state == "unlinked":
        return _Pairing(hidden=False, warning=W_UNLINKED)
    return _Pairing(hidden=False)


def _cleanup_operator(session: Session, completion: RunCompletion) -> tuple[str | None, str | None]:
    """完了にした片付けを終えた人の作業者IDと名前。"""
    cleanup = session.get(RunEvent, completion.cleanup_event_id)
    op = session.get(Operator, cleanup.ended_by) if cleanup and cleanup.ended_by else None
    return (op.worker_id, op.name) if op else (None, None)


def _ng(session: Session, group: KittingGroup, lot_no: str, side1_kno: str | None) -> tuple[int, int, list[str]]:
    """その面だけのNG数(面1・面2)。空は0。面1の行では面2は0。"""
    notes: list[str] = []
    if group.run_no == 1:
        return _latest_ng(session, lot_no, 1, group.kitting_no, notes), 0, notes
    ng1 = _latest_ng(session, lot_no, 1, side1_kno, notes) if side1_kno else 0
    return ng1, _latest_ng(session, lot_no, 2, group.kitting_no, notes), notes


def _latest_ng(session: Session, lot_no: str, side: int, side_kno: str, notes: list[str]) -> int:
    """NGが出た面の計画への、最新の入力。面1と面2の両方の画面で入力されていたら、新しいほうを使い、notes に残す。"""
    rows = list(session.scalars(select(RunNgInput).where(
        RunNgInput.lot_no == lot_no, RunNgInput.side == side, RunNgInput.side_kitting_no == side_kno,
    ).order_by(RunNgInput.entered_at, RunNgInput.id)))
    if not rows:
        return 0
    by_screen = {r.kitting_no: r.ng_qty for r in rows}
    if len(set(by_screen.values())) > 1:
        notes.append(f"ロットNo. {lot_no} の面{side}のNGが、面1と面2の両方の画面で入力されています(新しいほうの値を使います)")
    return rows[-1].ng_qty
