"""K社製品ロット管理票の、ファイルNo.ごとの内容(管理No と工程の行)の登録・コピー・履歴。管理画面から管理者が編集する。

保存のたびに版を足す(物理削除しない。前の版を見られる)。audit_log にも残す。印刷(識別票のページ)は最後の版を読むだけ。
詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import PLAN_CANCELLED, ControlSheetVersion, Operator, Plan
from app.db.session import write_transaction
from app.services import audit
from app.services.errors import NotFound, RuleViolation

MAX_ROWS = 100
MIN_PRINT_ROWS = 8  # 印刷する行の数の下限。登録した行がこれより少ないときは、下に空の行を足す(様式の4〜8の行と同じく、ライン名の欄に斜線)
Kind = Literal["internal", "external", "none"]  # 区分: 社内 / 社外 / なし
Link = Literal["none", "run1", "run2", "xray"]  # 将来の自動入力のための対応(今は印刷に使わない)


class ControlRow(BaseModel):
    """工程の行1つ。"""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=100, description="工程名(日本語。空でもよい = 手で書く行)")
    name_vi: str | None = Field(default=None, max_length=200, description="工程名のベトナム語(任意)")
    kind: Kind = "none"
    procedure: str = Field(default="", max_length=2000, description="作業要領・注意点(複数行)")
    use_line: bool = Field(default=True, description="ライン名の欄を使うか(使わない行は斜線を引く)")
    link: Link = "none"


class ControlSheetOut(BaseModel):
    file_no: str
    version: int
    manager_no: str
    rows: list[ControlRow]
    action: str
    copied_from: str | None
    saved_by_name: str | None
    saved_at: datetime


class ControlSheetSummaryOut(BaseModel):
    file_no: str
    registered: bool
    version: int | None
    manager_no: str | None
    row_count: int | None
    saved_by_name: str | None
    saved_at: datetime | None
    product_name: str | None  # 今の計画にあるファイルNo.のとき、その製品名(未登録を見つける手がかり)
    in_plans: bool  # 今の(取り消されていない)計画にある


class ControlSheetPrintOut(BaseModel):
    """印刷に使う内容。rows は登録した行 + 8行になるまでの空の行(use_line=False)。未登録のときは registered=False で、管理No は空、空の8行。"""

    registered: bool
    manager_no: str
    rows: list[ControlRow]


def check_file_no(file_no: str) -> str:
    key = file_no.strip()
    if not key or len(key) > 20:
        raise RuleViolation("ファイルNo.を入れてください(20文字まで)")
    return key


def _clean_rows(rows: list[ControlRow]) -> list[ControlRow]:
    if len(rows) > MAX_ROWS:
        raise RuleViolation(f"工程の行は {MAX_ROWS} 行までです")
    return [r.model_copy(update={"name": r.name.strip(), "name_vi": (r.name_vi or "").strip() or None, "procedure": r.procedure.rstrip()}) for r in rows]


def _out(session: Session, v: ControlSheetVersion) -> ControlSheetOut:
    by = session.get(Operator, v.saved_by)
    return ControlSheetOut(
        file_no=v.file_no, version=v.version, manager_no=v.manager_no, rows=[ControlRow(**r) for r in json.loads(v.rows_json)],
        action=v.action, copied_from=v.copied_from, saved_by_name=by.name if by else None, saved_at=v.saved_at,
    )


def _versions(session: Session, file_no: str | None = None):  # noqa: ANN202
    stmt = select(ControlSheetVersion).order_by(ControlSheetVersion.file_no, ControlSheetVersion.version.desc())
    return session.scalars(stmt.where(ControlSheetVersion.file_no == file_no) if file_no is not None else stmt)


def get_current(session: Session, file_no: str) -> ControlSheetOut | None:
    v = next(iter(_versions(session, file_no)), None)
    return _out(session, v) if v else None


def get_version(session: Session, file_no: str, version: int) -> ControlSheetOut:
    v = session.scalars(select(ControlSheetVersion).where(ControlSheetVersion.file_no == file_no, ControlSheetVersion.version == version)).first()
    if v is None:
        raise NotFound("その版は見つかりません")
    return _out(session, v)


def history(session: Session, file_no: str) -> list[ControlSheetOut]:
    """新しい版から順に。"""
    return [_out(session, v) for v in _versions(session, file_no)]


def print_data(session: Session, file_no: str) -> ControlSheetPrintOut:
    cur = get_current(session, file_no)
    rows = list(cur.rows) if cur else []
    rows += [ControlRow(use_line=False) for _ in range(MIN_PRINT_ROWS - len(rows))]
    return ControlSheetPrintOut(registered=cur is not None, manager_no=cur.manager_no if cur else "", rows=rows)


def _snapshot(s: ControlSheetOut) -> dict:
    return {"version": s.version, "manager_no": s.manager_no, "rows": [r.model_dump() for r in s.rows]}


def _add(session: Session, admin: Operator, key: str, manager_no: str, rows: list[ControlRow], action: str, copied_from: str | None) -> ControlSheetOut:
    before = get_current(session, key)
    v = ControlSheetVersion(
        file_no=key, version=(before.version if before else 0) + 1, manager_no=manager_no, rows_json=json.dumps([r.model_dump() for r in rows], ensure_ascii=False),
        action=action, copied_from=copied_from, saved_by=admin.id, saved_at=clock.now(),
    )
    session.add(v)
    session.flush()
    after = {"version": v.version, "manager_no": manager_no, "rows": [r.model_dump() for r in rows], **({"copied_from": copied_from} if copied_from else {})}
    audit.record_change(session, admin.id, ControlSheetVersion.__tablename__, key, f"control_sheet_{action}", _snapshot(before) if before else None, after)
    session.commit()
    return _out(session, v)


def save(session: Session, admin: Operator, file_no: str, manager_no: str, rows: list[ControlRow]) -> ControlSheetOut:
    """内容を保存する(新しい版を足す)。今の内容と同じなら、版は足さず今の版を返す。"""
    key, manager_no, rows = check_file_no(file_no), manager_no.strip(), _clean_rows(rows)
    with write_transaction(session):
        cur = get_current(session, key)
        if cur and cur.manager_no == manager_no and cur.rows == rows:
            return cur
        return _add(session, admin, key, manager_no, rows, "save", None)


def copy_from(session: Session, admin: Operator, file_no: str, source_file_no: str) -> ControlSheetOut:
    """別のファイルNo.の内容(工程の行)をコピーして、まだ登録していないファイルNo.に新しく作る。管理No はファイルNo.ごとに違うのでコピーしない。"""
    key, source = check_file_no(file_no), check_file_no(source_file_no)
    with write_transaction(session):
        src = get_current(session, source)
        if src is None:
            raise NotFound(f"コピー元のファイルNo.({source})は登録されていません")
        if get_current(session, key) is not None:
            raise RuleViolation(f"ファイルNo.({key})はすでに登録されています。コピーは新しく作るときだけです")
        return _add(session, admin, key, "", src.rows, "copy", source)


def list_sheets(session: Session) -> list[ControlSheetSummaryOut]:
    """登録済みのファイルNo.と、今の計画にあって未登録のファイルNo.(未登録を先に)。"""
    latest: dict[str, ControlSheetOut] = {}
    for v in _versions(session):  # ファイルNo.ごとに版の新しい順
        if v.file_no not in latest:
            latest[v.file_no] = _out(session, v)
    products: dict[str, str] = {}
    for file_no, name in session.execute(select(Plan.file_no, Plan.product_name).where(Plan.status != PLAN_CANCELLED).order_by(Plan.planned_start.desc())):
        products.setdefault(file_no, name)
    out = []
    for file_no in set(latest) | set(products):
        s = latest.get(file_no)
        out.append(ControlSheetSummaryOut(
            file_no=file_no, registered=s is not None, version=s.version if s else None, manager_no=s.manager_no if s else None,
            row_count=len(s.rows) if s else None, saved_by_name=s.saved_by_name if s else None, saved_at=s.saved_at if s else None,
            product_name=products.get(file_no), in_plans=file_no in products,
        ))
    return sorted(out, key=lambda x: (x.registered, x.file_no))
