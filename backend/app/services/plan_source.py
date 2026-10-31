"""ロットごとに、最後に書き込まれた月次DBを正とし、同期で使う計画を決める(開発指針 6.1)。DBに触らない。

詳細: docs/design/legacy-integration.md
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.core.clock import JST
from app.integration.legacy_plans import LegacyPlan, MonthlyDbRead, ReadWarning, StaleInfo
from app.services.plan_diff import PlanKey

_NO_TIME = datetime.min.replace(tzinfo=JST)


@dataclass
class SourceSelection:
    plans: list[LegacyPlan] = field(default_factory=list)  # 同期で使う計画(正とするDBの有効な計画)
    warnings: list[ReadWarning] = field(default_factory=list)
    lot_sources: dict[str, str] = field(default_factory=dict)  # ロットNo. → 正とするDBのフォルダ名
    plan_sources: dict[PlanKey, str] = field(default_factory=dict)  # 計画 → 正とするDBのフォルダ名
    stale: dict[PlanKey, StaleInfo] = field(default_factory=dict)  # 正とするDBのビュー v_plan_stale の判定(ビューのあるDBの計画だけ)
    no_stale_view: set[PlanKey] = field(default_factory=set)  # 正とするDBにビューが無い(読めない)計画。判定は「分からない」

    @property
    def known_lots(self) -> set[str]:
        """どこかの月次DBにあるロット。"""
        return set(self.lot_sources)


def _rank(db: MonthlyDbRead, lot: str) -> tuple:
    t = db.result.lot_last_written[lot]
    # 時刻が読めないロットは最も古い扱い。最後はフォルダ名で決め、結果を毎回同じにする
    return (t is not None, t or _NO_TIME, db.file_mtime, db.name)


def _lot_content(db: MonthlyDbRead, lot: str) -> dict[PlanKey, tuple]:
    return {p.key: p.content() for p in db.result.plans if p.lot_no == lot}


NO_STALE_VIEW = ("[{name}] 古い計画の判定(ビュー v_plan_stale)がありません。新しく「出し直し」の取消はせず、"
                 "前の「出し直し」の取消もそのままにします(既存アプリ 5.0.0 以降でこの月次DBを一度開くと、できます)")
UNDECIDED_REASONS = {
    "date_unparsable": "計画の開始日か終了日が空か読めない",
    "no_period": "最新の取り込みの日時が読めず期間が決まらない",
    "no_latest_batch": "最新の取り込みが無い",
}


def _undecided_warnings(db: MonthlyDbRead, sel: SourceSelection) -> list[ReadWarning]:
    """古い計画かどうか判定できなかった計画(古くないものとして扱う)の件数を、理由ごとに警告にする。"""
    counts: dict[str, int] = {}
    for key, info in (db.result.stale or {}).items():
        if sel.plan_sources.get(key) == db.name and info.reason in UNDECIDED_REASONS:
            counts[info.reason] = counts.get(info.reason, 0) + 1
    return [ReadWarning(None, None, f"[{db.name}] 古い計画かどうか判定できない計画が{n}件あります({UNDECIDED_REASONS[r]}。古くないものとして扱います)")
            for r, n in sorted(counts.items())]


def choose_sources(dbs: Sequence[MonthlyDbRead]) -> SourceSelection:
    sel = SourceSelection()
    lots = sorted({lot for db in dbs for lot in db.result.lot_last_written})
    for lot in lots:
        candidates = [db for db in dbs if lot in db.result.lot_last_written]
        winner = max(candidates, key=lambda db: _rank(db, lot))
        sel.lot_sources[lot] = winner.name

        t = winner.result.lot_last_written[lot]
        tied = [db for db in candidates if db is not winner and db.result.lot_last_written[lot] == t]
        if tied:
            winner_content = _lot_content(winner, lot)
            differ = [db.name for db in tied if _lot_content(db, lot) != winner_content]
            if differ:
                names = "、".join([winner.name, *differ])
                sel.warnings.append(ReadWarning(None, None, lot_no=lot, message=(
                    f"ロットの最終書き込み時刻が同じで内容が異なる月次DBがあります({names})。"
                    f"ファイルの更新日時が新しい「{winner.name}」を正とします"
                )))

    for db in dbs:
        adopted = 0
        for p in db.result.plans:
            if sel.lot_sources.get(p.lot_no) == db.name:
                sel.plans.append(p)
                sel.plan_sources[p.key] = db.name
                adopted += 1
                if db.result.stale is None:
                    sel.no_stale_view.add(p.key)
                elif p.key in db.result.stale:
                    sel.stale[p.key] = db.result.stale[p.key]
        if adopted and db.result.stale is None:
            sel.warnings.append(ReadWarning(None, None, NO_STALE_VIEW.format(name=db.name)))
        sel.warnings += _undecided_warnings(db, sel)
        # 警告は、正とするDBの行のものだけ残す(ロットが分からない警告はすべて残す)
        for w in db.result.warnings:
            if w.lot_no is None or sel.lot_sources.get(w.lot_no) == db.name:
                sel.warnings.append(w)
    return sel
