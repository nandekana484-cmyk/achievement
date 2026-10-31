"""開発用のコマンド: マスタの追加と一覧、画面の確認用のデータ。APIでは公開しない(管理画面とログインは後で作る)。

backend フォルダで、venv の中で実行する。対象は config.toml(GENBA_CONFIG)の paths.database。

    python -m app.cli operators list
    python -m app.cli operators add 山田
    python -m app.cli equipment list [--line S]
    python -m app.cli equipment add S マウンター1 [--vi "Máy gắn 1"]
    python -m app.cli equipment set-vi <ID> "Máy gắn 1"     # 空の文字列 "" で消す
    python -m app.cli reasons list
    python -m app.cli reasons set-vi <ID> "Tìm linh kiện"
    python -m app.cli lines list
    python -m app.cli admin set-password --worker-id K0042   # 管理画面のパスワード(入力は画面に出ない)
    python -m app.cli ip list                                  # アクセス制限(許可するIPアドレス)。管理画面に入れなくなったときの緊急用
    python -m app.cli ip add 192.168.3.0/24 [--scope admin] [--note "タブレット"]
    python -m app.cli ip remove <番号か範囲>                    # 無効にする(履歴は残る)
    python -m app.cli ip disable-all                           # すべて無効にして、制限をなくす
    python -m app.cli demo-seed --line S --date 2026-10-21
"""

from __future__ import annotations

import argparse
import datetime as dt
import getpass
import sys
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_config
from app.db.migrate import upgrade_to_head
from app.db.models import Equipment, Line, Operator, Reason
from app.db.session import get_sessionmaker, init_db
from app.domain.normalize import normalize_mounting_line
from app.services import admin_auth, ip_allowlist, masters
from app.services.demo_seed import seed_demo, seed_handover
from app.services.errors import NotFound, RuleViolation

DEMO_REFUSED = "config.toml に paths.legacy_app_dir が設定されているため、確認用のデータは入れません(実データと混ざらないように)"
OPERATOR_ADD_REFUSED = ("config.toml に paths.legacy_app_dir が設定されているため、作業者は追加できません"
                        "(作業者は既存アプリの master.db から読み込みます)")


def _yes(flag: bool) -> str:
    return "○" if flag else "-"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.cli", description="マスタの追加と一覧、確認用のデータ(開発用)")
    sub = p.add_subparsers(dest="target", required=True)

    ops = sub.add_parser("operators", help="作業者").add_subparsers(dest="action", required=True)
    ops.add_parser("list", help="一覧")
    add = ops.add_parser("add", help="追加")
    add.add_argument("name")
    add.add_argument("--id", default=None, help="作業者ID(32文字まで。画面でIDから呼び出すときに使う)")
    add.add_argument("--sort", type=int, default=None, help="表示順(省略すると最後)")
    add.add_argument("--admin", action="store_true", help="管理者にする(管理画面に入れる。開発用)")

    eq = sub.add_parser("equipment", help="設備").add_subparsers(dest="action", required=True)
    eq_list = eq.add_parser("list", help="一覧")
    eq_list.add_argument("--line", default=None, help="ラインで絞る")
    eq_add = eq.add_parser("add", help="追加")
    eq_add.add_argument("line")
    eq_add.add_argument("name")
    eq_add.add_argument("--sort", type=int, default=None, help="表示順(省略すると最後)")
    eq_add.add_argument("--vi", default=None, help="ベトナム語の名前(省略すると、画面は日本語の名前を出す)")
    _add_set_vi(eq)

    rs = sub.add_parser("reasons", help="理由").add_subparsers(dest="action", required=True)
    rs.add_parser("list", help="一覧")
    _add_set_vi(rs)
    sub.add_parser("lines", help="ライン").add_subparsers(dest="action", required=True).add_parser("list", help="一覧")

    adm = sub.add_parser("admin", help="管理画面").add_subparsers(dest="action", required=True)
    pw = adm.add_parser("set-password", help="管理者のパスワードを設定する(最初の設定とリセット)")
    pw.add_argument("--worker-id", required=True, help="作業者ID(既存アプリの役割が admin の作業者)")
    pw.add_argument("--stdin", action="store_true", help="パスワードを標準入力の1行目から読む(画面の確認の自動化用)")

    ip = sub.add_parser("ip", help="アクセス制限(許可するIPアドレス。サーバーのPCで使う緊急用)").add_subparsers(dest="action", required=True)
    ip.add_parser("list", help="一覧")
    ip_add = ip.add_parser("add", help="追加(1台か、192.168.3.0/24 のような範囲)")
    ip_add.add_argument("network")
    ip_add.add_argument("--scope", choices=("field", "admin"), default="field", help="field = 現場用(既定)、admin = 管理画面用")
    ip_add.add_argument("--note", default=None)
    ip_rm = ip.add_parser("remove", help="無効にする(番号か範囲で指定。履歴は残る)")
    ip_rm.add_argument("which", metavar="番号か範囲")
    ip.add_parser("disable-all", help="有効な範囲をすべて無効にする(制限がなくなる)")

    demo = sub.add_parser("demo-seed", help="画面の確認用の計画・作業者・設備を入れる")
    demo.add_argument("--line", required=True)
    demo.add_argument("--date", required=True, type=dt.date.fromisoformat, help="YYYY-MM-DD")
    demo.add_argument("--handover", action="store_true", help="引き継ぎの確認の確認用の計画(出し直しで古くなった計画と、出し直し後の計画)だけを入れる")
    demo.add_argument("--lot-suffix", default="", help="ロットNo.の末尾に付ける文字(ほかのラインの確認用のデータとロットを分けるとき)")
    return p


def _add_set_vi(actions) -> None:  # noqa: ANN001
    p = actions.add_parser("set-vi", help="ベトナム語の名前を登録する(空の文字列で消す)")
    p.add_argument("id", type=int)
    p.add_argument("name_vi")


def _list_operators(s: Session, _args: argparse.Namespace) -> None:
    for o in s.scalars(select(Operator).order_by(Operator.sort_order, Operator.id)):
        print(f"{o.id}\t{o.name}\t表示順 {o.sort_order}\t{'' if o.active else '(無効)'}\t"
              f"作業者ID {o.worker_id or '-'}\t{o.role}\t{o.source}")


def _add_operator(s: Session, args: argparse.Namespace) -> None:
    o = masters.add_operator(s, args.name, args.sort, worker_id=args.id, role="admin" if args.admin else "operator")
    print(f"作業者を追加しました: 番号 {o.id} {o.name}(作業者ID {o.worker_id or 'なし'})")


def _read_stdin_line() -> str:
    """標準入力の1行目。PowerShell 5.1 から渡すと先頭に BOM が付くので、BOM 付きの UTF-8 として読む。"""
    raw = sys.stdin.buffer.readline()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode(sys.stdin.encoding or "utf-8", errors="replace")
    return text.rstrip("\r\n")


def _set_password(s: Session, args: argparse.Namespace) -> None:
    admin_auth.admin_for_password(s, args.worker_id)  # 管理者でなければ、パスワードを聞く前に断る
    if args.stdin:
        password = _read_stdin_line()
    else:
        password = getpass.getpass("新しいパスワード(8文字以上。入力した文字は画面に出ません): ")
        if getpass.getpass("確認のため、もう一度: ") != password:
            raise RuleViolation("2回の入力が違います。設定していません")
    op = admin_auth.set_password(s, args.worker_id, password)
    print(f"管理画面のパスワードを設定しました: {op.name}(作業者ID {op.worker_id})")


def _list_equipment(s: Session, args: argparse.Namespace) -> None:
    stmt = select(Equipment).order_by(Equipment.line_code, Equipment.sort_order, Equipment.id)
    if args.line:
        stmt = stmt.where(Equipment.line_code == normalize_mounting_line(args.line))
    for e in s.scalars(stmt):
        print(f"{e.id}\t{e.line_code}\t{e.name}\tベトナム語 {e.name_vi or '-'}\t表示順 {e.sort_order}\t{'' if e.active else '(無効)'}")


def _add_equipment(s: Session, args: argparse.Namespace) -> None:
    e = masters.add_equipment(s, args.line, args.name, args.sort, name_vi=args.vi)
    print(f"設備を追加しました: ID {e.id} {e.line_code} {e.name}(ベトナム語 {e.name_vi or 'なし'})")


def _set_vi(model):  # noqa: ANN001, ANN202
    def run(s: Session, args: argparse.Namespace) -> None:
        row = masters.set_name_vi(s, model, args.id, args.name_vi)
        print(f"ベトナム語の名前を登録しました: ID {row.id} {row.name} → {row.name_vi or '(なし。日本語の名前を出す)'}")
    return run


def _list_reasons(s: Session, _args: argparse.Namespace) -> None:
    print("ID\t名前\tベトナム語\t区分\t稼働率に含める\t設備必須\t記入必須\t付帯作業\t再開理由")
    for r in s.scalars(select(Reason).order_by(Reason.sort_order, Reason.id)):
        print(f"{r.id}\t{r.name}\t{r.name_vi or '-'}\t{'ロス' if r.category == 'loss' else 'ロス以外'}\t"
              f"{_yes(r.counts_in_utilization)}\t{_yes(r.requires_equipment)}\t{_yes(r.requires_text)}\t"
              f"{_yes(r.usable_as_line_event)}\t{_yes(r.usable_as_restart)}")


def _list_lines(s: Session, _args: argparse.Namespace) -> None:
    for line in s.scalars(select(Line).order_by(Line.sort_order, Line.line_code)):
        print(f"{line.line_code}\t{line.name}\t表示順 {line.sort_order}\t{'' if line.active else '(無効)'}")


def _demo_seed(s: Session, args: argparse.Namespace) -> None:
    if args.handover:
        old, new = seed_handover(s, args.line, args.date)
        print(f"引き継ぎの確認用の計画を入れました: 古い計画 {old}(出し直しで古くなった)、出し直し後 {new}")
        return
    knos = seed_demo(s, args.line, args.date, args.lot_suffix)
    unique = list(dict.fromkeys(knos))
    print(f"確認用のデータを入れました({args.date}、ライン {normalize_mounting_line(args.line)}): "
          f"計画 {len(knos)}件(キッティングNo. {len(unique)}件)")
    for kno in unique:
        print(f"  {kno}({knos.count(kno)}ロット)")


def _list_ip(s: Session, _args: argparse.Namespace) -> None:
    rows = ip_allowlist.list_rows(s)
    lists = ip_allowlist.load_lists(s)
    print(f"アクセス制限: 現場用 {len(lists.field)}件、管理画面用 {len(lists.admin)}件が有効"
          f"({'制限なし' if not lists.field and not lists.admin else '制限あり。127.0.0.1 と ::1 は常に許可'})")
    for r in rows:
        print(f"{r.id}\t{'現場用' if r.scope == 'field' else '管理画面用'}\t{r.network}\t{'' if r.active else '(無効)'}\t{r.note or ''}")


def _add_ip(s: Session, args: argparse.Namespace) -> None:
    r = ip_allowlist.add_network(s, None, args.network, args.scope, args.note)
    print(f"追加しました: 番号 {r.id} {'現場用' if r.scope == 'field' else '管理画面用'} {r.network}(最大5秒で動いているアプリに反映されます)")


def _remove_ip(s: Session, args: argparse.Namespace) -> None:
    from app.domain.networks import parse_network

    rows = ip_allowlist.list_rows(s)
    if args.which.isdigit():
        hits = [r for r in rows if r.id == int(args.which)]
    else:
        try:
            net = str(parse_network(args.which))
        except ValueError as e:
            raise RuleViolation(str(e)) from None
        hits = [r for r in rows if r.active and r.network == net]
    if not hits:
        raise NotFound(f"「{args.which}」に当たる範囲が見つかりません(python -m app.cli ip list で確かめてください)")
    for r in hits:
        ip_allowlist.disable_network(s, None, r.id)
        print(f"無効にしました: 番号 {r.id} {r.network}")


def _disable_all_ip(s: Session, _args: argparse.Namespace) -> None:
    print(f"有効な範囲を {ip_allowlist.disable_all(s)}件 無効にしました。アクセス制限はなくなりました(最大5秒で反映されます)")


_COMMANDS = {
    ("ip", "list"): _list_ip,
    ("ip", "add"): _add_ip,
    ("ip", "remove"): _remove_ip,
    ("ip", "disable-all"): _disable_all_ip,
    ("operators", "list"): _list_operators,
    ("operators", "add"): _add_operator,
    ("equipment", "list"): _list_equipment,
    ("equipment", "add"): _add_equipment,
    ("equipment", "set-vi"): _set_vi(Equipment),
    ("reasons", "list"): _list_reasons,
    ("reasons", "set-vi"): _set_vi(Reason),
    ("admin", "set-password"): _set_password,
    ("lines", "list"): _list_lines,
    ("demo-seed", None): _demo_seed,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = get_config()
    if args.target == "demo-seed" and config.paths.legacy_app_dir is not None:
        print(f"エラー: {DEMO_REFUSED}", file=sys.stderr)
        return 1
    if (args.target, getattr(args, "action", None)) == ("operators", "add") and config.paths.legacy_app_dir is not None:
        print(f"エラー: {OPERATOR_ADD_REFUSED}", file=sys.stderr)
        return 1
    engine = init_db(config.paths.database)
    upgrade_to_head(engine)
    try:
        with get_sessionmaker()() as s:
            _COMMANDS[(args.target, getattr(args, "action", None))](s, args)
    except (RuleViolation, NotFound) as e:
        print(f"エラー: {e.message}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
