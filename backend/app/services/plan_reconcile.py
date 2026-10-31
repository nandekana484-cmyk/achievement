"""出し直しで残る古い計画の扱い(計画の同期から呼ぶ)。DBは実績のキッティングNo.を読むだけ。

- 古い計画(既存アプリのビュー v_plan_stale の is_stale=1 かつ judge_reason='stale')で、実績が無い: 取消(理由「出し直し」)
- 古い計画で、実績がある: 取り消さない。警告を出し、管理画面の「引き継ぎの確認」の対象にする
- ビューが無い・読めない月次DBの計画: 新しく取り消さず、前の「出し直し」の取消も元に戻さない
詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import select, union
from sqlalchemy.orm import Session

from app.db.models import (
    CANCEL_REISSUED,
    PLAN_ACTIVE,
    PLAN_CANCELLED,
    Plan,
    RunCompletion,
    RunEvent,
    RunInput,
    RunNgInput,
)
from app.integration.legacy_plans import ReadWarning, StaleInfo
from app.services.plan_diff import PlanKey
from app.services.plan_source import SourceSelection

STALE_WITH_ACTUALS = ("出し直しで古くなりましたが、実績があるため取り消しません。"
                      "管理画面の「引き継ぎの確認」で、新しいキッティングNo.へ移すか確かめてください")


def kitting_nos_with_actuals(session: Session) -> set[str]:
    """実績があるキッティングNo.(取り消していない工程の記録、備考、NG数、完了のどれかがある)。"""
    stmt = union(
        select(RunEvent.kitting_no).where(RunEvent.voided_at.is_(None)),
        select(RunInput.kitting_no), select(RunNgInput.kitting_no), select(RunCompletion.kitting_no),
    )
    return {k for (k,) in session.execute(stmt)}


@dataclass
class Reconcile:
    cancel: list[PlanKey] = field(default_factory=list)  # 有効 → 取消(理由「出し直し」)
    exclude: set[PlanKey] = field(default_factory=set)  # 追加・復活・更新をしない(古い計画、または前の取消を保つ計画)
    warnings: list[ReadWarning] = field(default_factory=list)


def reconcile_stale(rows: Mapping[PlanKey, Plan], sel: SourceSelection, with_actuals: set[str]) -> Reconcile:
    """正とするDBの計画を、古い計画の判定で振り分ける。"""
    out = Reconcile()
    for p in sel.plans:
        key = p.key
        row = rows.get(key)
        info = sel.stale.get(key)
        if info is not None and info.stale:
            if key[0] in with_actuals:
                out.warnings.append(ReadWarning(p.legacy_plan_item_id, key[0], lot_no=key[1], message=STALE_WITH_ACTUALS))
            else:
                out.exclude.add(key)  # 実績が無いので、守る必要がない(計画終了が過去でも取り消す)
                if row is not None and row.status == PLAN_ACTIVE:
                    out.cancel.append(key)
        elif key in sel.no_stale_view and row is not None and row.status == PLAN_CANCELLED and row.cancel_reason == CANCEL_REISSUED:
            out.exclude.add(key)  # 判定が分からない間は、前の「出し直し」の取消を元に戻さない
    return out


def apply_stale_flags(row: Plan, info: StaleInfo | None) -> None:
    """ビューの判定を plans に写す(判定が無い計画は前の値のまま)。"""
    if info is None:
        return
    row.is_stale = info.stale
    row.replacement_kitting_no = info.replacement_kitting_no if info.stale else None
    row.replacement_count = info.replacement_count if info.stale else 0
