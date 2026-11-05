"""管理表の内容を Excel のブックから一括で取り込む(AD-28): 確かめるだけ(DBに書かない)と、登録。

ブックはサーバーの中だけで読み、残さない(読み終えたら捨てる)。読んだ中身はログに書かない(件数とエラーの理由だけ)。
登録は、1回の取り込みを1つの単位として履歴に残し(control_sheet_imports)、audit_log にも残す。詳細: docs/design/control-sheet.md
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
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
from app.services.control_sheet_carry import carry_over
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


class LostOut(BaseModel):
    """引き継げずに消える、今の内容の行のベトナム語と対応(工程名が変わった・消えた行)。row は今の内容の行の番号。"""

    row: int
    name: str
    name_vi: str | None
    link: str


class ImportSheetOut(BaseModel):
    sheet_name: str
    file_no: str | None
    status: Status
    reason: str | None
    row_count: int | None
    manager_no: str | None
    overwrites_manual: bool  # 変更ありで、今の内容が管理画面で作った・直したもの(取り込みで上書きされる)
    current_version: int | None  # 確かめたときの今の版(新規は None)。登録のとき、変わっていれば断る
    carried: int  # 工程名のベトナム語・対応を、今の内容の同じ工程名の行から引き継いだ行の数
    lost: list[LostOut]  # 引き継げずに消えるもの
    changes: list[ChangeOut]
    changes_more: int


class ImportPreviewOut(BaseModel):
    filename: str
    sha256: str  # 確かめたブックの SHA-256(16進数)。登録のとき一緒に送り、同じブックか照らし合わせる
    sheets: list[ImportSheetOut]
    counts: dict[str, int]  # 状態ごとのシートの数


class ImportResultOut(BaseModel):
    import_id: int
    filename: str
    registered: int


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


def diff(current: ControlSheetOut, manager_no: str, new_rows: list[ControlRow]) -> tuple[list[ChangeOut], int]:
    """今の内容との違い(管理No、行数、行ごとの工程名・作業要領・区分・ライン名の欄)。"""
    out: list[ChangeOut] = []
    if current.manager_no != manager_no:
        out.append(ChangeOut(field="manager_no", row=None, before=current.manager_no, after=manager_no))
    if len(current.rows) != len(new_rows):
        out.append(ChangeOut(field="row_count", row=None, before=str(len(current.rows)), after=str(len(new_rows))))
    for i in range(max(len(current.rows), len(new_rows))):
        for field in ("name", "procedure", "kind", "use_line"):
            before, after = _rows_text(current.rows, i, field), _rows_text(new_rows, i, field)
            if before != after:
                out.append(ChangeOut(field=field, row=i + 1, before=before, after=after))  # type: ignore[arg-type]
    return out[:MAX_CHANGES], max(0, len(out) - MAX_CHANGES)


def _same(current: ControlSheetOut, manager_no: str, rows: list[ControlRow]) -> bool:
    """取り込みで作る内容(ベトナム語と対応は引き継いだもの)と、今の内容が同じか。"""
    return current.manager_no == manager_no and current.rows == rows


@dataclass(frozen=True)
class Classified:
    sheet: ImportSheetOut
    parsed: ParsedSheet | None  # 登録できるシートだけ
    rows: list[ControlRow] | None  # 登録する行(ベトナム語と対応を引き継いだもの)


class Expected(BaseModel):
    """確かめたときの、ファイルNo.の状態と今の版(登録のとき、変わっていないか照らし合わせる)。version は新規なら 0。"""

    status: Literal["new", "changed"]
    version: int


class ApplyMeta(BaseModel):
    """登録のとき、ブックと一緒に送るもの。"""

    file_nos: list[str]  # 登録するファイルNo.
    sha256: str  # 確かめたブックの SHA-256
    states: dict[str, Expected]  # 登録するファイルNo.ごとの、確かめたときの状態


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


def _empty(o: Outcome) -> Classified:
    sheet = ImportSheetOut(sheet_name=o.sheet_name, file_no=o.file_no, status="skipped" if o.skipped else "error", reason=o.skipped or o.error, row_count=None,
                           manager_no=None, overwrites_manual=False, current_version=None, carried=0, lost=[], changes=[], changes_more=0)
    return Classified(sheet, None, None)


def classify(session: Session, outcomes: list[Outcome]) -> list[Classified]:
    """読んだ結果を、今の内容と比べて、新規 / 変更あり / 変更なし / 飛ばした / エラーにする。今の内容に同じ工程名の行があれば、ベトナム語と対応を引き継ぐ。"""
    latest = latest_map(session)
    result = []
    for o in outcomes:
        if o.skipped or o.error or o.parsed is None:
            result.append(_empty(o))
            continue
        p, cur = o.parsed, latest.get(o.parsed.file_no)
        carry = carry_over(cur.rows, p.rows) if cur is not None else None
        rows = carry.rows if carry else p.rows
        status: Status = "new" if cur is None else "unchanged" if _same(cur, p.manager_no, rows) else "changed"
        changes, more = diff(cur, p.manager_no, rows) if status == "changed" and cur is not None else ([], 0)
        sheet = ImportSheetOut(
            sheet_name=o.sheet_name, file_no=p.file_no, status=status, reason=None, row_count=len(rows), manager_no=p.manager_no,
            overwrites_manual=status == "changed" and cur is not None and cur.action != "import", current_version=cur.version if cur else None,
            carried=carry.carried if carry else 0, lost=[LostOut(row=x.row, name=x.name, name_vi=x.name_vi, link=x.link) for x in carry.lost] if carry else [],
            changes=changes, changes_more=more,
        )
        result.append(Classified(sheet, p, rows))
    return result


def preview(session: Session, data: bytes, filename: str) -> ImportPreviewOut:
    """確かめるだけ。DBには書かない。ブックの SHA-256 を返す(登録のとき、同じブックか照らし合わせる。ブックは残さない)。"""
    filename = clean_filename(filename)
    sheets = [c.sheet for c in classify(session, read_book(data, filename))]
    counts = Counter(s.status for s in sheets)
    log.info("管理表の取り込みを確かめました: シート %d、新規 %d、変更あり %d、変更なし %d、飛ばした %d、エラー %d", len(sheets),
             counts["new"], counts["changed"], counts["unchanged"], counts["skipped"], counts["error"])
    for s in sheets:
        if s.status == "error":
            log.info("管理表の取り込み: シート「%s」はエラー: %s", s.sheet_name, s.reason)  # 理由だけ(中身は書かない)
    return ImportPreviewOut(filename=filename, sha256=hashlib.sha256(data).hexdigest(), sheets=sheets, counts=dict(counts))


def _check_unchanged_since_preview(classified: list[Classified], meta: ApplyMeta) -> None:
    """選ばれたファイルNo.の状態(新規 / 変更あり)と今の版が、確かめたときと同じか。変わっていれば(間に管理画面で直された、など)断る。"""
    by_file = {c.sheet.file_no: c.sheet for c in classified if c.sheet.file_no}
    changed = []
    for file_no in meta.file_nos:
        now, expected = by_file.get(file_no), meta.states.get(file_no)
        if now is None or expected is None or now.status != expected.status or (now.current_version or 0) != expected.version:
            changed.append(file_no)
    if changed:
        raise RuleViolation(f"確かめたあとに、ファイルNo.({', '.join(changed[:10])}{'…' if len(changed) > 10 else ''})の内容が変わりました。もう一度確かめてください")


def apply_import(session: Session, admin: Operator, data: bytes, filename: str, meta: ApplyMeta) -> ImportResultOut:
    """選んだファイルNo.(新規・変更ありのもの)を登録する。確かめたブックと同じ SHA-256、確かめたときと同じ状態でなければ断る。1回の取り込みを1つの単位として履歴に残す。"""
    filename = clean_filename(filename)
    if hashlib.sha256(data).hexdigest() != meta.sha256.lower():
        raise RuleViolation("確かめたブックと違います。もう一度確かめてください")
    if not meta.file_nos:
        raise RuleViolation("登録するシートが選ばれていません")
    outcomes = read_book(data, filename)  # 確かめたときと同じ読み方。読むのは書き込みのロックの外(時間がかかるため)
    with write_transaction(session):
        classified = classify(session, outcomes)  # ロックの中で、今の内容と比べ直す
        _check_unchanged_since_preview(classified, meta)
        todo = {c.sheet.file_no: c for c in classified if c.sheet.file_no in set(meta.file_nos) and c.sheet.status in ("new", "changed") and c.parsed is not None}
        imp = ControlSheetImport(filename=filename, imported_by=admin.id, imported_at=clock.now(), sheet_count=len(outcomes), registered_count=len(todo))
        session.add(imp)
        session.flush()
        for file_no, c in todo.items():
            add_version(session, admin, file_no, c.sheet.manager_no or "", c.rows or [], "import", import_id=imp.id, commit=False)
        audit.record_change(session, admin.id, ControlSheetImport.__tablename__, str(imp.id), "control_sheet_import_batch", None,
                            {"filename": filename, "sheets": len(outcomes), "registered": len(todo), "file_nos": sorted(todo)})
        session.commit()
    log.info("管理表の取り込みを登録しました: 取り込み %d、登録 %d 件", imp.id, len(todo))
    return ImportResultOut(import_id=imp.id, filename=filename, registered=len(todo))


def import_history(session: Session, limit: int = 50) -> list[ImportHistoryOut]:
    """取り込みの履歴(新しい順)。"""
    out = []
    for i in session.scalars(select(ControlSheetImport).order_by(ControlSheetImport.id.desc()).limit(limit)):
        by = session.get(Operator, i.imported_by)
        out.append(ImportHistoryOut(id=i.id, filename=i.filename, imported_by_name=by.name if by else None, imported_at=i.imported_at,
                                    sheet_count=i.sheet_count, registered_count=i.registered_count))
    return out
