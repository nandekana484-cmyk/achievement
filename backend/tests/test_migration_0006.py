"""マイグレーション 0006(実績をキッティングNo.の単位にする)。開発用の記録の移し方と、重なりがあれば止まること。"""

import pytest
from alembic import command
from sqlalchemy import text

from app.db.migrate import alembic_config, upgrade_to_head
from app.db.session import make_engine

T = "'2026-10-21 09:00:00.000000'"


def _at_0005(tmp_path):
    e = make_engine(tmp_path / "old.db")
    cfg = alembic_config()
    with e.begin() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0005")
        c.execute(text("INSERT INTO operators (name, active, sort_order) VALUES ('山田', 1, 10)"))
        c.execute(text("INSERT INTO lines (line_code, name, active, sort_order) VALUES ('S', 'Sライン', 1, 10)"))
        for lot in ("L1", "L2"):
            c.execute(text(
                "INSERT INTO plans (kitting_no, lot_no, file_no, line_code, product_name, run_no, planned_qty, delete_flag,"
                " legacy_plan_item_id, legacy_version, issue_date, issue_seq, status, first_seen_at, updated_at)"
                f" VALUES ('K1', '{lot}', '0722', 'S', '基板', 2, 100, 0, 1, 1, '2025-10-14', 1, 'active', {T}, {T})"
            ))
    return e


def _event(c, id_, lot, step="setup", seq=1):
    c.execute(text(
        "INSERT INTO run_events (id, kitting_no, lot_no, step_type, seq, start_at, started_by, start_request_id, created_at)"
        f" VALUES ({id_}, 'K1', '{lot}', '{step}', {seq}, {T}, 1, 'r{id_}', {T})"
    ))


def test_records_are_moved_to_kitting_unit(tmp_path):
    e = _at_0005(tmp_path)
    with e.begin() as c:
        _event(c, 1, "L1")
        _event(c, 2, "L1", "production")
        c.execute(text("INSERT INTO run_inputs (kitting_no, lot_no, kind, value, entered_by, entered_at, request_id)"
                       f" VALUES ('K1', 'L2', 'ng_qty', '3', 1, {T}, 'n1'), ('K1', 'L1', 'remark', 'メモ', 1, {T}, 'm1')"))

    upgrade_to_head(e)

    with e.connect() as c:
        assert c.execute(text("SELECT id, kitting_no, step_type FROM run_events ORDER BY id")).all() == [
            (1, "K1", "setup"), (2, "K1", "production"),
        ]
        assert c.execute(text("SELECT kitting_no, kind, value FROM run_inputs")).all() == [("K1", "remark", "メモ")]
        # それまでのNG数は、計画の面(2)でNGが出たものとして移す
        assert c.execute(text("SELECT kitting_no, lot_no, side, side_kitting_no, ng_qty FROM run_ng_inputs")).all() == [
            ("K1", "L2", 2, "K1", 3),
        ]
        cols = {r[1] for r in c.execute(text("PRAGMA table_info(run_events)"))}
        assert "lot_no" not in cols
    e.dispose()


def test_0007_keeps_operators_referenced_by_records(tmp_path):
    # 0007 は表を作り直さないので、工程の記録が作業者を参照していても止まらない
    e = _at_0005(tmp_path)
    with e.begin() as c:
        _event(c, 1, "L1")
    upgrade_to_head(e)
    with e.connect() as c:
        assert c.execute(text("SELECT name, worker_id, role, source FROM operators")).all() == [("山田", None, "operator", "local")]
        assert c.execute(text("SELECT started_by FROM run_events")).scalar_one() == 1
    e.dispose()


def test_stops_when_records_overlap(tmp_path):
    e = _at_0005(tmp_path)
    with e.begin() as c:
        _event(c, 1, "L1")
        _event(c, 2, "L2")  # 同じキッティングNo.の別のロットにも段取りの記録がある → まとめると重なる

    with pytest.raises(RuntimeError, match="K1"):
        upgrade_to_head(e)
    with e.connect() as c:  # 何も変えずに止まる
        assert c.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0005"
        assert c.execute(text("SELECT count(*) FROM run_events")).scalar_one() == 2
    e.dispose()
