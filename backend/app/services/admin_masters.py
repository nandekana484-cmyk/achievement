"""管理画面のマスタの管理(設備・理由・ライン・作業者)。変更はすべて audit_log に残す。行は消さず、無効にする。

使っている理由や設備を無効にしても、過去の記録は理由・設備の番号で持っているので表示は変わらない。詳細: docs/design/admin.md
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Equipment, Line, Operator, Reason
from app.db.session import write_transaction
from app.domain.normalize import normalize_mounting_line
from app.services.audit import diff_fields, record_change
from app.services.errors import NotFound, RuleViolation

CATEGORIES = ("loss", "non_loss")
_REASON_FLAGS = ("requires_equipment", "requires_text", "usable_as_line_event", "usable_as_restart", "counts_in_utilization")


class EquipmentAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_code: str
    name: str
    name_vi: str | None
    sort_order: int
    active: bool


class ReasonAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_vi: str | None
    category: str
    requires_equipment: bool
    requires_text: bool
    usable_as_line_event: bool
    usable_as_restart: bool
    counts_in_utilization: bool
    sort_order: int
    active: bool


class LineAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_code: str
    name: str
    sort_order: int
    active: bool
    auto_named: bool  # 名前が自動で付けた形(「<記号>ライン」)のまま


class OperatorAdminOut(BaseModel):
    id: int
    name: str
    worker_id: str | None
    role: str
    active: bool
    source: str  # legacy=既存アプリから読み込み / local=開発用に追加
    has_password: bool  # 管理画面のパスワードが設定されているか


def _clean(changes: dict[str, Any]) -> dict[str, Any]:
    """名前の前後の空白を除き、ベトナム語の名前の空は None にする。名前の空は断る。"""
    out = dict(changes)
    if "name" in out:
        out["name"] = (out["name"] or "").strip()
        if not out["name"]:
            raise RuleViolation("名前が空です")
    if "name_vi" in out:
        out["name_vi"] = (out["name_vi"] or "").strip() or None
    if "category" in out and out["category"] not in CATEGORIES:
        raise RuleViolation("区分は loss(ロス)か non_loss(ロス以外)にしてください")
    return out


def _next_sort(session: Session, model) -> int:  # noqa: ANN001
    return (session.scalar(select(func.max(model.sort_order))) or 0) + 10


def _update(session: Session, actor_id: int, row: Any, table: str, key: str, changes: dict[str, Any]) -> Any:
    """変わった項目だけを書き換え、audit_log に残す(変わらなければ何もしない)。"""
    changes = _clean(changes)
    with write_transaction(session):
        before, after = diff_fields(row, changes)
        if after:
            for k, v in after.items():
                setattr(row, k, v)
            record_change(session, actor_id, table, key, "update", before, after)
        session.commit()
    return row


def _create(session: Session, actor_id: int, row: Any, table: str, fields: dict[str, Any]) -> Any:
    with write_transaction(session):
        session.add(row)
        session.flush()
        key = str(row.line_code if table == "lines" else row.id)
        record_change(session, actor_id, table, key, "create", None, {k: getattr(row, k) for k in fields})
        session.commit()
    return row


# --- 設備 ---

def list_equipment(session: Session) -> list[Equipment]:
    return list(session.scalars(select(Equipment).order_by(Equipment.line_code, Equipment.sort_order, Equipment.id)))


def add_equipment(session: Session, actor_id: int, line_code: str, fields: dict[str, Any]) -> Equipment:
    fields = _clean({"name": fields.get("name"), "name_vi": fields.get("name_vi"), "sort_order": fields.get("sort_order")})
    line = session.get(Line, normalize_mounting_line(line_code))
    if line is None:
        raise RuleViolation(f"ライン「{line_code}」が登録されていません")
    if fields["sort_order"] is None:
        fields["sort_order"] = _next_sort(session, Equipment)
    row = Equipment(line_code=line.line_code, active=True, **fields)
    return _create(session, actor_id, row, "equipment", ["line_code", *fields, "active"])


def update_equipment(session: Session, actor_id: int, equipment_id: int, changes: dict[str, Any]) -> Equipment:
    row = session.get(Equipment, equipment_id)
    if row is None:
        raise NotFound(f"設備(ID {equipment_id})が見つかりません")
    return _update(session, actor_id, row, "equipment", str(equipment_id), changes)


# --- 理由 ---

def list_reasons(session: Session) -> list[Reason]:
    return list(session.scalars(select(Reason).order_by(Reason.sort_order, Reason.id)))


def add_reason(session: Session, actor_id: int, fields: dict[str, Any]) -> Reason:
    fields = _clean({k: v for k, v in fields.items() if v is not None} | {"name": fields.get("name")})
    fields.setdefault("category", "loss")
    fields.setdefault("sort_order", _next_sort(session, Reason))
    for flag in _REASON_FLAGS:
        fields.setdefault(flag, False)
    return _create(session, actor_id, Reason(active=True, **fields), "reasons", [*fields, "active"])


def update_reason(session: Session, actor_id: int, reason_id: int, changes: dict[str, Any]) -> Reason:
    row = session.get(Reason, reason_id)
    if row is None:
        raise NotFound(f"理由(ID {reason_id})が見つかりません")
    return _update(session, actor_id, row, "reasons", str(reason_id), changes)


# --- ライン ---

def list_lines(session: Session) -> list[Line]:
    return list(session.scalars(select(Line).order_by(Line.sort_order, Line.line_code)))


def update_line(session: Session, actor_id: int, line_code: str, changes: dict[str, Any]) -> Line:
    row = session.get(Line, normalize_mounting_line(line_code))
    if row is None:
        raise NotFound(f"ライン「{line_code}」が見つかりません")
    return _update(session, actor_id, row, "lines", row.line_code, changes)


# --- 作業者(見るだけ。開発用の作業者だけ追加できる) ---

def list_operators(session: Session) -> list[OperatorAdminOut]:
    from app.services.admin_auth import has_password

    ops = session.scalars(select(Operator).order_by(Operator.name, Operator.worker_id, Operator.id))
    return [
        OperatorAdminOut(id=o.id, name=o.name, worker_id=o.worker_id, role=o.role, active=o.active, source=o.source,
                         has_password=has_password(session, o.id))
        for o in ops
    ]


def add_local_operator(session: Session, actor_id: int, name: str, worker_id: str | None, legacy_app_dir_set: bool) -> Operator:
    """開発用の作業者を足す。既存アプリから作業者を読み込む環境(legacy_app_dir あり)では断る。"""
    from app.services import masters

    if legacy_app_dir_set:
        raise RuleViolation("作業者は既存アプリから読み込むため、ここでは追加できません(開発用の環境だけで追加できます)")
    op = masters.add_operator(session, name, worker_id=worker_id)
    with write_transaction(session):
        record_change(session, actor_id, "operators", str(op.id), "create", None,
                      {"name": op.name, "worker_id": op.worker_id, "source": op.source})
        session.commit()
    return op
