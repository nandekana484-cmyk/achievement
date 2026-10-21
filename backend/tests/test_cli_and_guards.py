"""開発用のコマンド(python -m app.cli)と、DB側の二重記録の防止。"""

from datetime import date, time

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


def test_demo_seed_inserts_plans_operators_and_equipment(cli_config, capsys, fake_clock):
    assert cli.main(["demo-seed", "--line", "s", "--date", "2026-10-21"]) == 0
    assert cli.main(["demo-seed", "--line", "S", "--date", "2026-10-21"]) == 0  # 何度実行しても同じ
    out = capsys.readouterr().out
    assert "計画 8件" in out and "0722-1-S-261014-01" in out

    from app.db.session import get_sessionmaker
    from app.services.board import get_board

    with get_sessionmaker()() as s:
        assert [o.name for o in s.scalars(select(Operator))] == ["山田", "佐藤"]
        assert s.scalar(select(func.count()).select_from(Line)) == 1
        b = get_board(s, "S", date(2026, 10, 21), time(8, 15))
    plans = {p.plan.kitting_no: p.plan for p in b.plans}
    # 過ぎて未着手の計画(3日前)は出ず、ほかの7件は表示範囲(10/20 20:15〜10/22 20:15)に出る
    assert len(plans) == 7 and "0950-1-S-261014-07" not in plans
    assert plans["0960-1-S-261014-08"].planned_end > b.display_end  # 表示範囲の終わりをまたぐ
    assert {(p.lot_no, p.run_no) for p in plans.values() if p.lot_no == "DEMO-001"} == {("DEMO-001", 1), ("DEMO-001", 2)}  # 組
    assert any(p.takt_sec is None for p in plans.values())  # タクトなし
    a, c = plans["0722-1-S-261014-01"], plans["0800-1-S-261014-03"]
    assert a.planned_start < c.planned_end and c.planned_start < a.planned_end  # 時間の重なり
    night = plans["0930-1-S-261014-05"]
    assert night.planned_end.date() == date(2026, 10, 22)  # 日付をまたぐ
    assert plans["0940-1-S-261014-06"].planned_start > b.workday_end  # 次の稼働日(境目の先)


def test_demo_seed_refuses_when_legacy_app_dir_is_set(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.toml"
    db = tmp_path / "real.db"
    cfg.write_text(f'[paths]\ndatabase = "{db.as_posix()}"\nlegacy_app_dir = "C:/work/inventory/dist"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    try:
        assert cli.main(["demo-seed", "--line", "S", "--date", "2026-10-21"]) == 1
    finally:
        get_config.cache_clear()
    assert "legacy_app_dir が設定されている" in capsys.readouterr().err
    assert not db.exists()  # DBに触らない


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
