"""開発用のコマンド: マスタの追加と一覧。APIでは公開しない(管理画面とログインは後で作る)。

backend フォルダで、venv の中で実行する。対象は config.toml(GENBA_CONFIG)の paths.database。

    python -m app.cli operators list
    python -m app.cli operators add 山田
    python -m app.cli equipment list [--line S]
    python -m app.cli equipment add S マウンター1
    python -m app.cli reasons list
    python -m app.cli lines list
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy import select

from app.core.config import get_config
from app.db.migrate import upgrade_to_head
from app.db.models import Equipment, Line, Operator, Reason
from app.db.session import get_sessionmaker, init_db
from app.domain.normalize import normalize_mounting_line
from app.services import masters
from app.services.errors import NotFound, RuleViolation


def _yes(flag: bool) -> str:
    return "○" if flag else "-"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.cli", description="マスタの追加と一覧(開発用)")
    sub = p.add_subparsers(dest="target", required=True)

    ops = sub.add_parser("operators", help="作業者").add_subparsers(dest="action", required=True)
    ops.add_parser("list", help="一覧")
    add = ops.add_parser("add", help="追加")
    add.add_argument("name")
    add.add_argument("--sort", type=int, default=None, help="表示順(省略すると最後)")

    eq = sub.add_parser("equipment", help="設備").add_subparsers(dest="action", required=True)
    eq_list = eq.add_parser("list", help="一覧")
    eq_list.add_argument("--line", default=None, help="ラインで絞る")
    eq_add = eq.add_parser("add", help="追加")
    eq_add.add_argument("line")
    eq_add.add_argument("name")
    eq_add.add_argument("--sort", type=int, default=None, help="表示順(省略すると最後)")

    sub.add_parser("reasons", help="理由").add_subparsers(dest="action", required=True).add_parser("list", help="一覧")
    sub.add_parser("lines", help="ライン").add_subparsers(dest="action", required=True).add_parser("list", help="一覧")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = get_config()
    engine = init_db(config.paths.database)
    upgrade_to_head(engine)
    try:
        with get_sessionmaker()() as s:
            match (args.target, args.action):
                case ("operators", "list"):
                    for o in s.scalars(select(Operator).order_by(Operator.sort_order, Operator.id)):
                        print(f"{o.id}\t{o.name}\t表示順 {o.sort_order}\t{'' if o.active else '(無効)'}")
                case ("operators", "add"):
                    o = masters.add_operator(s, args.name, args.sort)
                    print(f"作業者を追加しました: ID {o.id} {o.name}")
                case ("equipment", "list"):
                    stmt = select(Equipment).order_by(Equipment.line_code, Equipment.sort_order, Equipment.id)
                    if args.line:
                        stmt = stmt.where(Equipment.line_code == normalize_mounting_line(args.line))
                    for e in s.scalars(stmt):
                        print(f"{e.id}\t{e.line_code}\t{e.name}\t表示順 {e.sort_order}\t{'' if e.active else '(無効)'}")
                case ("equipment", "add"):
                    e = masters.add_equipment(s, args.line, args.name, args.sort)
                    print(f"設備を追加しました: ID {e.id} {e.line_code} {e.name}")
                case ("reasons", "list"):
                    print("ID\t名前\t区分\t稼働率に含める\t設備必須\t記入必須\t付帯作業\t再開理由")
                    for r in s.scalars(select(Reason).order_by(Reason.sort_order, Reason.id)):
                        print(f"{r.id}\t{r.name}\t{'ロス' if r.category == 'loss' else 'ロス以外'}\t"
                              f"{_yes(r.counts_in_utilization)}\t{_yes(r.requires_equipment)}\t{_yes(r.requires_text)}\t"
                              f"{_yes(r.usable_as_line_event)}\t{_yes(r.usable_as_restart)}")
                case ("lines", "list"):
                    for line in s.scalars(select(Line).order_by(Line.sort_order, Line.line_code)):
                        print(f"{line.line_code}\t{line.name}\t表示順 {line.sort_order}\t{'' if line.active else '(無効)'}")
    except (RuleViolation, NotFound) as e:
        print(f"エラー: {e.message}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
