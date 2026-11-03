"""書き出した行の記録(exported_rows)と、書き出し後に紐づけが変わった計画の一覧(管理画面)。

すでに書き出した計画の紐づけが変わると、既存アプリの値は管理者が直す必要がある。変わったことは断らず、一覧に出して「確認済み」にできる。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import ActualsExport, ExportedRow, Operator, SideLink
from app.db.session import write_transaction
from app.services import audit
from app.services.errors import NotFound
from app.services.side_link_store import ACTION_LINK, ACTION_SKIP, ACTION_UNLINK, who


def record_exported_rows(session: Session, export_id: int, rows: Iterable) -> None:
    """書き出した行(ActualsRowOut)を記録する。"""
    for r in rows:
        session.add(ExportedRow(export_id=export_id, kitting_no=r.kitting_no, lot_no=r.lot_no, side1_kitting_no=r.side1_kitting_no))


def last_export_at(session: Session, kitting_nos: set[str]) -> dt.datetime | None:
    """それらのキッティングNo.のどれかを書き出した、最後の書き出し日時(書き出していなければ None)。"""
    if not kitting_nos:
        return None
    return session.scalar(
        select(func.max(ActualsExport.exported_at)).join(ExportedRow, ExportedRow.export_id == ActualsExport.id)
        .where(or_(ExportedRow.kitting_no.in_(kitting_nos), ExportedRow.side1_kitting_no.in_(kitting_nos))))


class LinkChangeOut(BaseModel):
    id: int
    side2_kitting_no: str | None
    previous_partner: str | None  # 変える前の相手
    new_partner: str | None  # 変えたあとの相手(外したときは空)
    action: str  # link / unlink / skip
    changed_by: str
    source: str  # field(現場の作業者)/ admin(管理者)
    changed_at: dt.datetime
    exported_at: dt.datetime  # 最後の書き出し日時(変えたときの)


def _out(session: Session, r: SideLink) -> LinkChangeOut:
    new = r.side1_kitting_no if r.action == ACTION_LINK else None
    return LinkChangeOut(id=r.id, side2_kitting_no=r.side2_kitting_no, previous_partner=r.previous_partner, new_partner=new,
                         action=r.action, changed_by=who(session, r.decided_by), source=r.source, changed_at=r.decided_at,
                         exported_at=r.exported_at)  # type: ignore[arg-type]  # 一覧は exported_at のある行だけ


def changes_after_export(session: Session) -> list[LinkChangeOut]:
    """書き出し済みだった計画の紐づけが変わり、管理者がまだ確認していないもの(新しい順)。"""
    rows = session.scalars(select(SideLink).where(
        SideLink.exported_at.is_not(None), SideLink.export_checked_at.is_(None), SideLink.action.in_((ACTION_LINK, ACTION_UNLINK, ACTION_SKIP)),
    ).order_by(SideLink.id.desc()))
    return [_out(session, r) for r in rows]


def mark_checked(session: Session, admin: Operator, change_id: int) -> LinkChangeOut:
    """管理者が「確認済み」にする(既存アプリの値を直したあと)。"""
    row = session.get(SideLink, change_id)
    if row is None or row.exported_at is None:
        raise NotFound(f"書き出し後の紐づけの変更(番号 {change_id})が見つかりません")
    with write_transaction(session):
        if row.export_checked_at is None:
            row.export_checked_by, row.export_checked_at = admin.id, clock.now()
            audit.record_change(session, admin.id, "side_links", str(row.id), "export_checked", {"checked": False}, {"checked": True})
        session.commit()
    return _out(session, row)
