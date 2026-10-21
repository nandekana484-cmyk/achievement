"""マスタ(ライン・作業者・設備・理由)の取得と追加。追加は今は開発用のコマンドからだけ。

詳細: docs/design/run-records.md
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Equipment, Line, Operator, Reason
from app.db.models.masters import default_line_name
from app.db.session import write_transaction
from app.domain.normalize import normalize_mounting_line
from app.domain.worker_id import MAX_LENGTH, worker_key
from app.services.errors import NotFound, RuleViolation
from app.services.views import EquipmentOut, LineOut, MastersOut, OperatorOut, ReasonOut


def get_line(session: Session, line_code: str) -> Line:
    """ラインを探す。記号は既存アプリと同じ規則で正規化してから探す。"""
    line = session.get(Line, normalize_mounting_line(line_code))
    if line is None:
        raise NotFound(f"ライン「{line_code}」が見つかりません")
    return line


def _next_sort_order(session: Session, model) -> int:  # noqa: ANN001
    return (session.scalar(select(func.max(model.sort_order))) or 0) + 10


def register_lines(session: Session, line_codes: Iterable[str]) -> list[str]:
    """まだ無いラインを登録する(コミットは呼び出し側)。登録した記号を返す。"""
    known = set(session.scalars(select(Line.line_code)))
    added: list[str] = []
    order = _next_sort_order(session, Line)
    for code in sorted({c for c in line_codes if c} - known):
        session.add(Line(line_code=code, name=default_line_name(code), active=True, sort_order=order))
        order += 10
        added.append(code)
    return added


def list_masters(session: Session, line_code: str | None = None) -> MastersOut:
    """有効なマスタを sort_order 順に返す。line_code を指定すると、設備はそのラインのものだけ。"""
    equipment = select(Equipment).where(Equipment.active.is_(True))
    if line_code is not None:
        equipment = equipment.where(Equipment.line_code == get_line(session, line_code).line_code)

    def active(model):  # noqa: ANN001, ANN202
        return session.scalars(select(model).where(model.active.is_(True)).order_by(model.sort_order, *model.__table__.primary_key))

    operators = session.scalars(select(Operator).where(Operator.active.is_(True)).order_by(Operator.name, Operator.worker_id, Operator.id))
    return MastersOut(
        lines=[LineOut.model_validate(x) for x in active(Line)],
        operators=[OperatorOut.model_validate(x) for x in operators],  # 名前順(同じ名前は作業者IDで区別する)
        equipment=[EquipmentOut.model_validate(x) for x in session.scalars(equipment.order_by(Equipment.sort_order, Equipment.id))],
        reasons=[ReasonOut.model_validate(x) for x in active(Reason)],
    )


def add_operator(
    session: Session, name: str, sort_order: int | None = None, worker_id: str | None = None, role: str = "operator",
) -> Operator:
    """開発用に作業者を足す(source=local)。既存アプリの作業者を読み込む環境では、開発用コマンドの側で断る。"""
    name = name.strip()
    if not name:
        raise RuleViolation("作業者の名前が空です")
    key = None
    if worker_id is not None:
        worker_id = worker_id.strip()
        key = worker_key(worker_id)
        if not key or len(worker_id) > MAX_LENGTH:
            raise RuleViolation(f"作業者IDは1〜{MAX_LENGTH}文字で入れてください")
    with write_transaction(session):
        if key and session.scalars(select(Operator).where(Operator.worker_key == key)).first() is not None:
            session.rollback()
            raise RuleViolation(f"作業者ID「{worker_id}」は、ほかの作業者と重なります(全角・半角、大文字・小文字の違いは区別しません)")
        op = Operator(name=name, active=True, worker_id=worker_id, worker_key=key, role=role, source="local",
                      sort_order=sort_order if sort_order is not None else _next_sort_order(session, Operator))
        session.add(op)
        session.commit()
    return op


def lookup_operator(session: Session, worker_id: str) -> Operator:
    """作業者IDで呼び出す(全角・半角、大文字・小文字の違いは無視)。有効な作業者だけ。"""
    key = worker_key(worker_id)
    op = session.scalars(select(Operator).where(Operator.worker_key == key, Operator.active.is_(True))).first() if key else None
    if op is None:
        raise NotFound("作業者IDが見つかりません")
    return op


def resolve_operator_ref(session: Session, operator_id: int | None, worker_id: str | None) -> int | None:
    """記録者の指定(内部の番号 operator_id か、作業者ID worker_id のどちらか)を、内部の番号にする。"""
    if operator_id is not None and worker_id is not None:
        raise RuleViolation("operator_id と worker_id は、どちらか一方だけを指定してください")
    if worker_id is not None:
        return lookup_operator(session, worker_id).id
    return operator_id


def add_equipment(
    session: Session, line_code: str, name: str, sort_order: int | None = None, name_vi: str | None = None,
) -> Equipment:
    name = name.strip()
    if not name:
        raise RuleViolation("設備の名前が空です")
    with write_transaction(session):
        try:
            line = get_line(session, line_code)
        except NotFound:
            session.rollback()
            raise RuleViolation(f"ライン「{line_code}」が登録されていません(ラインは計画の同期で自動登録されます)") from None
        eq = Equipment(line_code=line.line_code, name=name, name_vi=_vi(name_vi), active=True,
                       sort_order=sort_order if sort_order is not None else _next_sort_order(session, Equipment))
        session.add(eq)
        session.commit()
    return eq


def get_active_operator(session: Session, operator_id: int) -> Operator:
    op = session.get(Operator, operator_id)
    if op is None or not op.active:
        raise RuleViolation(f"作業者(内部の番号 {operator_id})が見つかりません")
    return op


def _vi(name_vi: str | None) -> str | None:
    """ベトナム語の名前。空なら None(画面は日本語の名前を出す)。"""
    return (name_vi or "").strip() or None


def set_name_vi(session: Session, model: type[Equipment] | type[Reason], row_id: int, name_vi: str | None) -> Equipment | Reason:
    """設備か理由のベトナム語の名前を変える。空にすると消す。"""
    with write_transaction(session):
        row = session.get(model, row_id)
        if row is None:
            session.rollback()
            raise NotFound(f"{'設備' if model is Equipment else '理由'}(ID {row_id})が見つかりません")
        row.name_vi = _vi(name_vi)
        session.commit()
    return row
