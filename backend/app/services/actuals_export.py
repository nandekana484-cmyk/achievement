"""実績の書き出し: 画面で直した数を確かめ、CSV を exchange_dir\\actuals\\ に保存し、履歴を残す。

書き出しても実績の記録は変えない(同じ内容を何回書き出しても、こちらの記録は変わらない。増えるのは履歴だけ)。
CSV は BOM 付きの UTF-8、改行は CRLF。保存は一時ファイル(.tmp)に書き終えてから .csv に改名する。
詳細: docs/design/actuals-export.md
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db.models import ActualsExport, Operator
from app.db.session import write_transaction
from app.services.actuals_rows import ActualsListOut, ActualsRowOut, build_rows
from app.services.errors import NotFound, RuleViolation

ACTUALS_FOLDER = "actuals"
FORMAT_VERSION = 2  # 書式版。列を変えたら上げる(既存アプリの取込口が、知らない版を断れるように)。2 = 「面1のキッティングNo.」を足した
HEADERS = ["書式版", "書き出し日時", "元のDB(フォルダ名)", "キッティングNo.", "ロットNo.", "ファイルNo.", "面", "日付", "生産数(累計)",
           "NG面1", "NG面2", "担当者ID", "面1のキッティングNo."]


class QuantityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kitting_no: str = Field(max_length=100)
    lot_no: str = Field(max_length=100)
    produced_qty: int = Field(ge=0, description="画面で直した生産数(累計)")


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: dt.date
    date_to: dt.date
    line_code: str | None = None
    quantities: list[QuantityIn] = Field(default_factory=list, description="直した行だけ送る(送らない行は割り振ったまま)")


class ExportOut(BaseModel):
    id: int
    exported_at: dt.datetime
    exported_by: str  # 名前(作業者ID)
    row_count: int
    file_name: str
    date_from: dt.date
    date_to: dt.date
    line_code: str | None


def apply_quantities(listing: ActualsListOut, quantities: list[QuantityIn]) -> list[ActualsRowOut]:
    """直した数を当て、キッティングNo.ごとに合計が累計と合うか確かめて、書き出す行を返す。合わなければ RuleViolation。"""
    by_key = {(r.kitting_no, r.lot_no): r for r in listing.rows}
    rows = {k: r.model_copy() for k, r in by_key.items()}
    for q in quantities:
        key = (q.kitting_no, q.lot_no)
        if key not in rows:
            raise RuleViolation(f"一覧に無い行です(キッティングNo. {q.kitting_no}、ロットNo. {q.lot_no})。一覧を読み直してください")
        rows[key].produced_qty = q.produced_qty
    sums: dict[str, int] = {}
    for r in rows.values():
        sums[r.kitting_no] = sums.get(r.kitting_no, r.kitting_hidden_qty) + r.produced_qty
    for r in rows.values():
        if sums[r.kitting_no] != r.kitting_produced_total:
            raise RuleViolation(
                f"キッティングNo. {r.kitting_no} のロットの生産数の合計({sums[r.kitting_no]})が、"
                f"記録の累計({r.kitting_produced_total})と一致しません。ロットの数を直してください")
    exportable = [r for r in rows.values() if r.exportable]
    if not exportable:
        raise RuleViolation("書き出せる行がありません(警告のある行は書き出しません)")
    return exportable


def actuals_csv(rows: list[ActualsRowOut], exported_at: dt.datetime) -> str:
    """CSV の文字列(BOM は保存とダウンロードのときに付ける)。

    書き出し日時は YYYY-MM-DD HH:MM:SS(日本時間、タイムゾーンなし)に固定する。
    面1のキッティングNo.は、面2の行でつながる面1(キー H か確定した組)があるときだけ入れる(NG面1 が 0 でも入れる)。
    """
    stamp = exported_at.astimezone(clock.JST).strftime("%Y-%m-%d %H:%M:%S")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(HEADERS)
    for r in rows:
        w.writerow([FORMAT_VERSION, stamp, r.source_db or "", r.kitting_no, r.lot_no, r.file_no, r.side, r.completed_on.isoformat(),
                    r.produced_qty, r.ng_side1, r.ng_side2, r.worker_id or "", r.side1_kitting_no or ""])
    return buf.getvalue()


def export_actuals(session: Session, admin: Operator, body: ExportIn, exchange_dir: Path, day_start: dt.time) -> ExportOut:
    """書き出す。CSV を保存してから履歴をコミットする(保存できなければ履歴も残さない)。"""
    with write_transaction(session):
        listing = build_rows(session, body.date_from, body.date_to, body.line_code, day_start)
        rows = apply_quantities(listing, body.quantities)
        now = clock.now()
        content = actuals_csv(rows, now)
        row = ActualsExport(exported_at=now, exported_by=admin.id, row_count=len(rows), file_name="",
                            date_from=body.date_from, date_to=body.date_to, line_code=body.line_code, content=content)
        session.add(row)
        session.flush()
        row.file_name = f"actuals_{now.astimezone(clock.JST):%Y%m%d_%H%M%S}_{row.id:04d}.csv"
        try:
            _save(exchange_dir / ACTUALS_FOLDER, row.file_name, content)
        except OSError as e:
            session.rollback()
            raise RuleViolation(f"書き出し先に保存できませんでした({exchange_dir / ACTUALS_FOLDER}): {e}") from e
        session.commit()
        return _out(session, row)


def _save(folder: Path, name: str, content: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"{name}.tmp"
    tmp.write_bytes(content.encode("utf-8-sig"))
    tmp.replace(folder / name)  # 読み手(既存アプリの取込口)は .csv だけを読む


def list_exports(session: Session, limit: int = 50) -> list[ExportOut]:
    """書き出しの履歴(新しい順)。"""
    rows = session.scalars(select(ActualsExport).order_by(ActualsExport.id.desc()).limit(limit))
    return [_out(session, r) for r in rows]


def export_file(session: Session, export_id: int) -> tuple[str, bytes]:
    """書き出した CSV(ファイル名と、BOM 付きの中身)。"""
    row = session.get(ActualsExport, export_id)
    if row is None:
        raise NotFound(f"書き出しの履歴(番号 {export_id})が見つかりません")
    return row.file_name, row.content.encode("utf-8-sig")


def _out(session: Session, row: ActualsExport) -> ExportOut:
    op = session.get(Operator, row.exported_by)
    who = f"{op.name}({op.worker_id})" if op and op.worker_id else (op.name if op else "")
    return ExportOut(id=row.id, exported_at=row.exported_at, exported_by=who, row_count=row.row_count,
                     file_name=row.file_name, date_from=row.date_from, date_to=row.date_to, line_code=row.line_code)
