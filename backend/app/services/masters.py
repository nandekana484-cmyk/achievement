"""マスタ(ライン・作業者・設備・理由)。

- ラインは計画の同期で自動登録する(name は "<記号>ライン")
- 作業者・設備の追加は、今は開発用のコマンド(python -m app.cli)からだけ行う。管理画面とログインは後で作る
- 行は消さない。使わなくなったものは active=False にする
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Equipment, Line, Operator, Reason
from app.db.session import write_transaction
from app.domain.normalize import normalize_mounting_line
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
        session.add(Line(line_code=code, name=f"{code}ライン", active=True, sort_order=order))
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

    return MastersOut(
        lines=[LineOut.model_validate(x) for x in active(Line)],
        operators=[OperatorOut.model_validate(x) for x in active(Operator)],
        equipment=[EquipmentOut.model_validate(x) for x in session.scalars(equipment.order_by(Equipment.sort_order, Equipment.id))],
        reasons=[ReasonOut.model_validate(x) for x in active(Reason)],
    )


def add_operator(session: Session, name: str, sort_order: int | None = None) -> Operator:
    name = name.strip()
    if not name:
        raise RuleViolation("作業者の名前が空です")
    with write_transaction(session):
        op = Operator(name=name, active=True,
                      sort_order=sort_order if sort_order is not None else _next_sort_order(session, Operator))
        session.add(op)
        session.commit()
    return op


def add_equipment(session: Session, line_code: str, name: str, sort_order: int | None = None) -> Equipment:
    name = name.strip()
    if not name:
        raise RuleViolation("設備の名前が空です")
    with write_transaction(session):
        try:
            line = get_line(session, line_code)
        except NotFound:
            session.rollback()
            raise RuleViolation(f"ライン「{line_code}」が登録されていません(ラインは計画の同期で自動登録されます)") from None
        eq = Equipment(line_code=line.line_code, name=name, active=True,
                       sort_order=sort_order if sort_order is not None else _next_sort_order(session, Equipment))
        session.add(eq)
        session.commit()
    return eq


def get_active_operator(session: Session, operator_id: int) -> Operator:
    op = session.get(Operator, operator_id)
    if op is None or not op.active:
        raise RuleViolation(f"作業者(ID {operator_id})が見つかりません")
    return op
