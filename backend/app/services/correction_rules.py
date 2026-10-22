"""実績の訂正の共通ルール(理由、現場で直せる範囲、時刻の確かめ)と、訂正の履歴の記録。違反は RuleViolation(409)。

詳細: docs/design/run-records.md
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import JST
from app.db.models import RunCorrection
from app.domain.corrections import CorrectionKind, CorrectionReason, CorrectionSource
from app.domain.workday import workday_of, workday_range
from app.services.errors import RuleViolation

OUT_OF_FIELD_RANGE = "この記録は現場の画面で直せる範囲(タイムテーブルの表示範囲)の外です。管理画面から直してください"


@dataclass(frozen=True)
class FieldScope:
    """現場の画面から直すときの範囲 = 今の稼働日の前後に margin_hours を足した範囲。管理画面から直すときは使わない。"""

    day_start: time
    margin_hours: int

    def window(self, now: datetime) -> tuple[datetime, datetime]:
        start, end = workday_range(workday_of(now, self.day_start), self.day_start)
        margin = timedelta(hours=self.margin_hours)
        return start - margin, end + margin


def source_of(scope: FieldScope | None) -> CorrectionSource:
    return CorrectionSource.FIELD if scope is not None else CorrectionSource.ADMIN


def fmt(t: datetime | None) -> str:
    """理由の文に入れる時刻(10/21 9:05)。"""
    if t is None:
        return ""
    local = t.astimezone(JST)
    return f"{local.month}/{local.day} {local.hour}:{local.minute:02d}"


def span_text(start: datetime, end: datetime | None) -> str:
    return f"{fmt(start)}〜{fmt(end)}" if end is not None else f"{fmt(start)}〜(終了していない)"


def check_reason(reason: str, note: str | None) -> tuple[CorrectionReason, str | None]:
    """訂正の理由(必須)と記入(その他では必須)。"""
    try:
        code = CorrectionReason(reason)
    except ValueError:
        raise RuleViolation("訂正の理由を選んでください(押し間違い・押し忘れ・数の入力の誤り・その他)") from None
    text = (note or "").strip() or None
    if code == CorrectionReason.OTHER and text is None:
        raise RuleViolation("理由が「その他」のときは、内容を記入してください")
    return code, text


def check_record_in_scope(scope: FieldScope | None, now: datetime, start: datetime, end: datetime | None) -> None:
    """現場の画面から直せるのは、開始か終了が範囲にある記録だけ。"""
    if scope is None:
        return
    lo, hi = scope.window(now)
    if not any(t is not None and lo <= t <= hi for t in (start, end)):
        raise RuleViolation(OUT_OF_FIELD_RANGE)


def check_new_times_in_scope(scope: FieldScope | None, now: datetime, times: Iterable[datetime | None]) -> None:
    """現場の画面から入れる時刻も、範囲の中だけ。"""
    if scope is None:
        return
    lo, hi = scope.window(now)
    if any(t is not None and not lo <= t <= hi for t in times):
        raise RuleViolation(f"現場の画面では、{fmt(lo)}〜{fmt(hi)} の時刻だけ入れられます。範囲の外の時刻は管理画面から直してください")


def check_order_and_future(start: datetime, end: datetime | None, now: datetime) -> None:
    """開始 < 終了、未来の時刻は不可。"""
    if start > now or (end is not None and end > now):
        raise RuleViolation("未来の時刻は入れられません")
    if end is not None and start >= end:
        raise RuleViolation("開始の時刻は、終了の時刻より前にしてください")


def conflicts(start: datetime, end: datetime | None, other_start: datetime, other_end: datetime | None,
              closed_may_overlap: bool) -> bool:
    """ほかの記録と矛盾するか。終了していない記録は今も続いているので、どちらかが終了していなければ重ねられない。

    closed_may_overlap: 終了した記録どうしは重なってよいか(生産の区切りどうしは重ならない)。
    """
    if closed_may_overlap and end is not None and other_end is not None:
        return False
    return start < (other_end or datetime.max.replace(tzinfo=JST)) and other_start < (end or datetime.max.replace(tzinfo=JST))


def json_value(v: Any) -> Any:
    return v.astimezone(JST).isoformat() if isinstance(v, datetime) else v


def changes_of(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """変わった項目ごとの変更前と変更後(JSON にできる値)。"""
    return [{"field": k, "before": json_value(before.get(k)), "after": json_value(after[k])}
            for k in after if before.get(k) != after[k]]


def record_correction(
    session: Session, *, target_table: str, target_id: int, kitting_no: str | None, line_code: str,
    kind: CorrectionKind, changes: list[dict[str, Any]], reason: CorrectionReason, note: str | None,
    corrected_by: int, now: datetime, scope: FieldScope | None, request_id: str,
) -> RunCorrection:
    row = RunCorrection(
        target_table=target_table, target_id=target_id, kitting_no=kitting_no, line_code=line_code, kind=kind.value,
        changes_json=json.dumps(changes, ensure_ascii=False), reason=reason.value, note=note, corrected_by=corrected_by,
        corrected_at=now, source=source_of(scope).value, request_id=request_id,
    )
    session.add(row)
    session.flush()
    return row
