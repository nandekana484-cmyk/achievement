"""効率の計算に使う、計画のまとまり(キッティングNo.)の目標タクトと丁取り数。

完了した計画は完了の写しの値、作業中の計画は今の値。ロットで違えば最初のロットの値を使い、警告を返す。
詳細: docs/design/metrics.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.integration.legacy.teitori import STATUS_OK
from app.services.completions import latest_completion
from app.services.kitting_plans import KittingGroup
from app.services.teitori_lookup import lookup_teitori

REASON_NO_TAKT = "no_takt"  # 目標タクトが無い


@dataclass(frozen=True)
class EfficiencyInputs:
    takt_sec: float | None  # 目標タクト(1枚あたりの秒)
    teitori: int | None
    teitori_status: str  # ok / 既存アプリの status / no_row
    warnings: list[str] = field(default_factory=list)

    @property
    def excluded_reason(self) -> str | None:
        """効率の計算から外す理由(丁取りの status か no_takt)。使えるなら None。1を仮定しない。"""
        if self.teitori_status != STATUS_OK:
            return self.teitori_status
        if self.teitori is None or self.teitori < 1:
            return "teitori_invalid"
        if self.takt_sec is None or self.takt_sec <= 0:
            return REASON_NO_TAKT
        return None


def inputs_for(session: Session, group: KittingGroup) -> EfficiencyInputs:
    """計画のまとまりの目標タクトと丁取り数(完了していれば完了の写し。写しに丁取りが無い古い完了は今の値)。"""
    warnings: list[str] = []
    kno = group.kitting_no
    if len({lot.takt_sec for lot in group.lots}) > 1:
        warnings.append(f"キッティングNo. {kno} のロットで目標タクトが違います(最初のロットの値を使います)")
    found = {lookup_teitori(session, lot.file_no, lot.line_code) for lot in group.lots}
    if len(found) > 1:
        warnings.append(f"キッティングNo. {kno} のロットで丁取りが違います(最初のロットの値を使います)")
    teitori, status = lookup_teitori(session, group.first.file_no, group.first.line_code)
    takt = group.takt_sec

    completion = latest_completion(session, kno)
    if completion is not None:
        takt = completion.takt_sec_snapshot
        if completion.teitori_status_snapshot is not None:
            teitori, status = completion.teitori_snapshot, completion.teitori_status_snapshot
    return EfficiencyInputs(takt, teitori, status, warnings)
