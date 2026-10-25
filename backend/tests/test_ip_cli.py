"""緊急用コマンド python -m app.cli ip ...(サーバーのPCで、管理画面に入れなくなったとき用)。"""

from __future__ import annotations

import pytest

from app import cli
from app.db.session import get_sessionmaker, init_db
from app.services import ip_allowlist


@pytest.fixture
def cli_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "cli.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    yield tmp_path / "cli.db"
    get_config.cache_clear()


def _lists(db):
    engine = init_db(db)
    try:
        with get_sessionmaker()() as s:
            return ip_allowlist.load_lists(s)
    finally:
        engine.dispose()


def test_add_list_remove_and_disable_all(cli_config, capsys):
    assert cli.main(["ip", "add", "192.168.3.0/24", "--note", "タブレット"]) == 0
    assert cli.main(["ip", "add", "192.168.9.5", "--scope", "admin"]) == 0
    assert cli.main(["ip", "add", "fd00::/64"]) == 0
    capsys.readouterr()
    assert cli.main(["ip", "list"]) == 0
    out = capsys.readouterr().out
    assert "現場用 2件、管理画面用 1件" in out and "制限あり" in out and "192.168.3.0/24" in out and "タブレット" in out
    lists = _lists(cli_config)
    assert [str(n) for n in lists.field] == ["192.168.3.0/24", "fd00::/64"] and [str(n) for n in lists.admin] == ["192.168.9.5/32"]

    assert cli.main(["ip", "remove", "192.168.3.0/24"]) == 0  # 範囲で指定
    assert cli.main(["ip", "remove", "3"]) == 0  # 番号で指定
    assert [str(n) for n in _lists(cli_config).field] == []
    capsys.readouterr()
    assert cli.main(["ip", "list"]) == 0
    assert "(無効)" in capsys.readouterr().out  # 履歴は残る

    assert cli.main(["ip", "disable-all"]) == 0
    assert "1件" in capsys.readouterr().out
    lists = _lists(cli_config)
    assert not lists.field and not lists.admin  # 制限がなくなる
    assert cli.main(["ip", "list"]) == 0
    assert "制限なし" in capsys.readouterr().out


def test_bad_input_and_unknown_target_fail_with_a_message(cli_config, capsys):
    assert cli.main(["ip", "add", "abc"]) == 1
    assert "書き方が正しくありません" in capsys.readouterr().err
    assert cli.main(["ip", "add", "0.0.0.0/0"]) == 1
    assert cli.main(["ip", "add", "10.0.0.0/8"]) == 0
    assert cli.main(["ip", "add", "10.1.2.3/8"]) == 1  # 同じ範囲
    assert "すでに登録されています" in capsys.readouterr().err
    assert cli.main(["ip", "remove", "999"]) == 1
    assert cli.main(["ip", "remove", "172.16.0.0/12"]) == 1
    assert "見つかりません" in capsys.readouterr().err
    assert cli.main(["ip", "remove", "zzz"]) == 1


def test_cli_works_even_when_the_admin_screen_is_unreachable(cli_config):
    """管理画面用の一覧から自分が外れていても、サーバーのPCの開発用コマンドは(自分を外すかの確認なしに)直せる。"""
    assert cli.main(["ip", "add", "192.168.9.5", "--scope", "admin"]) == 0
    assert cli.main(["ip", "disable-all"]) == 0
    assert not _lists(cli_config).admin
