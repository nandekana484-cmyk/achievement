"""開発用のコマンド(python -m app.cli)と、DB側の二重記録の防止。"""

import pytest
from sqlalchemy import func, select

from app import cli
from app.db.models import ApiRequest, Line, Operator, RunEvent
from app.domain.steps import StepType
from app.services import masters, run_records
from app.services.errors import RuleViolation
from app.services.idempotency import CONCURRENT_CONFLICT
from app.services.plan_sync import run_plan_sync
from legacy_fixture import insert_plan


@pytest.fixture
def cli_config(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "cli.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    yield tmp_path / "cli.db"
    get_config.cache_clear()


def test_cli_operators(cli_config, capsys):
    assert cli.main(["operators", "add", "山田"]) == 0
    assert cli.main(["operators", "add", "佐藤", "--sort", "5"]) == 0
    capsys.readouterr()

    assert cli.main(["operators", "list"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split("\t")[1] for line in out] == ["佐藤", "山田"]  # 表示順


def test_cli_equipment_requires_registered_line(cli_config, capsys):
    assert cli.main(["equipment", "add", "S", "マウンター1"]) == 1
    assert "ライン「S」が登録されていません" in capsys.readouterr().err

    from app.db.session import get_sessionmaker

    cli.main(["lines", "list"])  # DBを作る
    with get_sessionmaker()() as s:
        s.add(Line(line_code="S", name="Sライン", active=True, sort_order=10))
        s.commit()
    capsys.readouterr()
    assert cli.main(["equipment", "add", "s", "マウンター1"]) == 0  # 記号は正規化する
    assert cli.main(["equipment", "list", "--line", "S"]) == 0
    assert "\tS\tマウンター1\t" in capsys.readouterr().out


def test_cli_reasons_list(cli_config, capsys):
    assert cli.main(["reasons", "list"]) == 0
    out = capsys.readouterr().out
    assert "マシントラブル\tロス\t-\t○\t-\t○\t○" in out
    assert "人員交代\tロス以外\t-\t-\t-\t-\t○" in out


def test_db_prevents_second_open_event(session_factory, legacy_app, legacy_db, fake_clock, monkeypatch):
    """確認をすり抜けても(同時の操作など)、DBの一意制約で二重の開始を防ぎ、409 の文にする。"""
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    with session_factory() as s:
        run_plan_sync(s, legacy_app)
        op = masters.add_operator(s, "山田").id
        run_records.start_step(s, "0722-1-S-251014-01", "L001", StepType.SETUP, "r1", operator_id=op)

    monkeypatch.setattr(run_records, "_open_event", lambda *_: None)  # 確認をすり抜けたことにする
    with session_factory() as s, pytest.raises(RuleViolation) as e:
        run_records.start_step(s, "0722-1-S-251014-01", "L001", StepType.SETUP, "r2", operator_id=op)

    assert e.value.message == CONCURRENT_CONFLICT
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(RunEvent)) == 1
        assert s.get(ApiRequest, "r2") is None  # 失敗した操作は記録しない
        assert s.scalar(select(func.count()).select_from(Operator)) == 1
