"""管理表の内容を Excel のブックから一括で取り込む(AD-28): 確かめるだけ(DBに書かない)と、登録。

ブックはサーバーの中だけで読み、残さない(読み終えたら捨てる)。読んだ中身はログに書かない(件数とエラーの理由だけ)。
登録は、1回の取り込みを1つの単位として履歴に残し(control_sheet_imports)、audit_log にも残す。詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import ControlSheetImport, Operator
from app.db.session import write_transaction
from app.services import audit
from app.services.control_sheet_book import open_sheets
from app.services.control_sheet_parse import ParsedSheet, SheetError, SheetSkipped, parse_sheet
from app.services.control_sheets import ControlRow, ControlSheetOut, add_version, latest_map
from app.services.errors import RuleViolation

log = logging.getLogger(__name__)
Status = Literal["new", "changed", "unchanged", "skipped", "error"]
MAX_CHANGES = 50  # 1シートに出す違いの数の上限(多いときは changes_more に件数)
KIND_LABEL = {"none": "なし", "internal": "社内", "external": "社外"}


class ChangeOut(BaseModel):
    """今の内容との違い1つ。row は工程の行の番号(1から。管理No・行数のときは None)。"""

    field: Literal["manager_no", "row_count", "name", "procedure", "kind", "use_line"]
    row: int | None
    before: str
    after: str


class ImportSheetOut(BaseModel):
    sheet_name: str
    file_no: str | None
    status: Status
    reason: str | None
    row_count: int | None
    manager_no: str | None
    overwrites_manual: bool  # 変更ありで、今の内容が管理画面で作った・直したもの(取り込みで上書きされる)
    changes: list[ChangeOut]
    changes_more: int


class ImportPreviewOut(BaseModel):
    filename: str
    sheets: list[ImportSheetOut]
    counts: dict[str, int]  # 状態ごとのシートの数


class ImportResultOut(BaseModel):
    import_id: int
    filename: str
    registered: int
    ignored: int  # 選ばれたが、登録の対象でなかった(状態が新規・変更あり以外に変わった)シートの数


class ImportHistoryOut(BaseModel):
    id: int
    filename: str
    imported_by_name: str | None
    imported_at: datetime
    sheet_count: int
    registered_count: int


def clean_filename(name: str) -> str:
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return base[:200] or "ブック"


def _rows_text(rows: list[ControlRow], i: int, field: str) -> str:
    if i >= len(rows):
        return ""
    value = getattr(rows[i], field)
    return KIND_LABEL[value] if field == "kind" else ("使う" if value else "使わない") if field == "use_line" else value


def diff(current: ControlSheetOut, new: ParsedSheet) -> tuple[list[ChangeOut], int]:
    """今の内容との違い(管理No、行数、行ごとの工程名・作業要領・区分・ライン名の欄)。"""
    out: list[ChangeOut] = []
    if current.manager_no != new.manager_no:
        out.append(ChangeOut(field="manager_no", row=None, before=current.manager_no, after=new.manager_no))
    if len(current.rows) != len(new.rows):
        out.append(ChangeOut(field="row_count", row=None, before=str(len(current.rows)), after=str(len(new.rows))))
    for i in range(max(len(current.rows), len(new.rows))):
        for field in ("name", "procedure", "kind", "use_line"):
            before, after = _rows_text(current.rows, i, field), _rows_text(new.rows, i, field)
            if before != after:
                out.append(ChangeOut(field=field, row=i + 1, before=before, after=after))  # type: ignore[arg-type]
    return out[:MAX_CHANGES], max(0, len(out) - MAX_CHANGES)


def _same(current: ControlSheetOut, new: ParsedSheet) -> bool:
    """取り込みが作る内容(工程名のベトナム語と対応は空)と、今の内容が同じか。管理画面で付けたベトナム語・対応があれば違いとする(取り込みで上書きされる)。"""
    return current.manager_no == new.manager_no and current.rows == new.rows


class Outcome(BaseModel):
    """1シートを読んだ結果(DBとの比較の前)。"""

    sheet_name: str
    file_no: str | None = None
    parsed: ParsedSheet | None = None
    skipped: str | None = None
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


def read_book(data: bytes, filename: str) -> list[Outcome]:
    """ブックを読む(DBには触れない)。シートごとに、読めた・飛ばした・エラー。同じファイルNo.のシートが複数あれば、2つ目からエラー。"""
    outcomes: list[Outcome] = []
    seen: dict[str, str] = {}
    for sheet in open_sheets(data, filename):
        try:
            parsed = parse_sheet(sheet)
        except SheetSkipped as e:
            outcomes.append(Outcome(sheet_name=sheet.name, skipped=str(e)))
        except SheetError as e:
            outcomes.append(Outcome(sheet_name=sheet.name, error=str(e)))
        else:
            if parsed.file_no in seen:
                outcomes.append(Outcome(sheet_name=sheet.name, file_no=parsed.file_no, error=f"同じファイルNo.のシート({seen[parsed.file_no]})がすでにあります"))
            else:
                seen[parsed.file_no] = sheet.name
                outcomes.append(Outcome(sheet_name=sheet.name, file_no=parsed.file_no, parsed=parsed))
    return outcomes


def classify(session: Session, outcomes: list[Outcome]) -> list[ImportSheetOut]:
    """読んだ結果を、今の内容と比べて、新規 / 変更あり / 変更なし / 飛ばした / エラーにする。"""
    latest = latest_map(session)
    result = []
    for o in outcomes:
        if o.skipped or o.error or o.parsed is None:
            result.append(ImportSheetOut(sheet_name=o.sheet_name, file_no=o.file_no, status="skipped" if o.skipped else "error", reason=o.skipped or o.error,
                                         row_count=None, manager_no=None, overwrites_manual=False, changes=[], changes_more=0))
            continue
        p, cur = o.parsed, latest.get(o.parsed.file_no)
        status: Status = "new" if cur is None else "unchanged" if _same(cur, p) else "changed"
        changes, more = diff(cur, p) if status == "changed" and cur is not None else ([], 0)
        result.append(ImportSheetOut(sheet_name=o.sheet_name, file_no=p.file_no, status=status, reason=None, row_count=len(p.rows), manager_no=p.manager_no,
                                     overwrites_manual=status == "changed" and cur is not None and cur.action != "import", changes=changes, changes_more=more))
    return result


def preview(session: Session, data: bytes, filename: str) -> ImportPreviewOut:
    """確かめるだけ。DBには書かない。"""
    filename = clean_filename(filename)
    sheets = classify(session, read_book(data, filename))
    counts = Counter(s.status for s in sheets)
    log.info("管理表の取り込みを確かめました: シート %d、新規 %d、変更あり %d、変更なし %d、飛ばした %d、エラー %d", len(sheets),
             counts["new"], counts["changed"], counts["unchanged"], counts["skipped"], counts["error"])
    for s in sheets:
        if s.status == "error":
            log.info("管理表の取り込み: シート「%s」はエラー: %s", s.sheet_name, s.reason)  # 理由だけ(中身は書かない)
    return ImportPreviewOut(filename=filename, sheets=sheets, counts=dict(counts))


def apply_import(session: Session, admin: Operator, data: bytes, filename: str, selected: list[str]) -> ImportResultOut:
    """選んだファイルNo.(新規・変更ありのもの)を登録する。1回の取り込みを1つの単位として履歴に残す。"""
    filename = clean_filename(filename)
    outcomes = read_book(data, filename)  # 読むのは書き込みのロックの外(時間がかかるため)
    wanted = set(selected)
    if not wanted:
        raise RuleViolation("登録するシートが選ばれていません")
    with write_transaction(session):
        sheets = classify(session, outcomes)  # ロックの中で、今の内容と比べ直す
        todo = {s.file_no for s in sheets if s.file_no in wanted and s.status in ("new", "changed")}
        imp = ControlSheetImport(filename=filename, imported_by=admin.id, imported_at=clock.now(), sheet_count=len(outcomes), registered_count=len(todo))
        session.add(imp)
        session.flush()
        for o in outcomes:
            if o.parsed is not None and o.parsed.file_no in todo:
                add_version(session, admin, o.parsed.file_no, o.parsed.manager_no, o.parsed.rows, "import", import_id=imp.id, commit=False)
        audit.record_change(session, admin.id, ControlSheetImport.__tablename__, str(imp.id), "control_sheet_import_batch", None,
                            {"filename": filename, "sheets": len(outcomes), "registered": len(todo), "file_nos": sorted(todo)})
        session.commit()
    log.info("管理表の取り込みを登録しました: 取り込み %d、登録 %d 件", imp.id, len(todo))
    return ImportResultOut(import_id=imp.id, filename=filename, registered=len(todo), ignored=len(wanted - todo))


def import_history(session: Session, limit: int = 50) -> list[ImportHistoryOut]:
    """取り込みの履歴(新しい順)。"""
    out = []
    for i in session.scalars(select(ControlSheetImport).order_by(ControlSheetImport.id.desc()).limit(limit)):
        by = session.get(Operator, i.imported_by)
        out.append(ImportHistoryOut(id=i.id, filename=i.filename, imported_by_name=by.name if by else None, imported_at=i.imported_at,
                                    sheet_count=i.sheet_count, registered_count=i.registered_count))
    return out
