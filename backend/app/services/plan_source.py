"""ロットごとに、正とする既存アプリの月次DBを決める(開発指針 6.1)。DBに触らない純粋な処理。

実績は計画(キッティングNo.+ロットNo.)に付けるものなので、計画がどの月次DBにあるかにはとらわれない。
棚卸の期間が重なり、既存アプリでDBを行き来することがよくあるため、同じロットが複数のDBにあるときは
「ロットごとに、最後に書き込まれたDB」を正とする。

- ロットの最終書き込み時刻 = そのDBのそのロットの全行(無効な行も含む)の MAX(updated_at)
  (既存アプリは、版の更新・削除(ソフト)・前月からの引き継ぎで updated_at を書き換える。
   バックアップから戻したDBは元の時刻のままなので、正にならない)
- 同じ時刻のときは、DBファイルの更新日時が新しいほうを正とする。内容が違えば警告を出す
- 同期で使う計画 = 各ロットについて、正とするDBの有効な計画だけ。
  正とするDBにそのロットの有効な行が無ければ(削除(ソフト)など)、そのロットの計画は「消えた」扱い
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from app.core.clock import JST
from app.integration.legacy_plans import LegacyPlan, MonthlyDbRead, ReadWarning
from app.services.plan_diff import PlanKey

_NO_TIME = datetime.min.replace(tzinfo=JST)


@dataclass
class SourceSelection:
    plans: list[LegacyPlan] = field(default_factory=list)  # 同期で使う計画(正とするDBの有効な計画)
    warnings: list[ReadWarning] = field(default_factory=list)
    lot_sources: dict[str, str] = field(default_factory=dict)  # ロットNo. → 正とするDBのフォルダ名
    plan_sources: dict[PlanKey, str] = field(default_factory=dict)  # 計画 → 正とするDBのフォルダ名

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
        for p in db.result.plans:
            if sel.lot_sources.get(p.lot_no) == db.name:
                sel.plans.append(p)
                sel.plan_sources[p.key] = db.name
        # 警告は、正とするDBの行のものだけ残す(ロットが分からない警告はすべて残す)
        for w in db.result.warnings:
            if w.lot_no is None or sel.lot_sources.get(w.lot_no) == db.name:
                sel.warnings.append(w)
    return sel
