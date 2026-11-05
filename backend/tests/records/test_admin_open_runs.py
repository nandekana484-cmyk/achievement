"""管理画面の「終了していない古い記録」(AD-23 2-b): 一覧の条件、終了時刻の検査、取り消し、run_corrections と audit_log、完了の処理。"""

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core.clock import JST
from app.db.models import AuditLog, RunCompletion, RunCorrection, RunEvent
from app.services import admin_auth, masters
from records_helpers import K1, K2, new_session, ok, start

PASSWORD = "right-pass-1"
H = {"X-Genba-Admin": "1"}
OLD = datetime(2026, 10, 10, 10, 0, tzinfo=JST)  # 今(10/21 8:00)の表示範囲を広げても入らない(限度は 10/18 8:15)


def login(client):
    return client.post("/api/admin/login", json={"worker_id": "K0042", "password": PASSWORD}, headers=H)


@pytest.fixture
def old_runs(client, staffed, fake_clock):
    """K1 は 10/10 に段取りを始めて終了していない。K2 は今、段取りを始めたところ(範囲の中)。"""
    now = fake_clock.current
    fake_clock.current = OLD
    ok(start(client, "setup", kitting_no=K1))
    fake_clock.current = now
    ok(start(client, "setup", kitting_no=K2))
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", PASSWORD)
    assert login(client).status_code == 200
    with new_session() as s:
        return {"old": s.scalars(select(RunEvent).where(RunEvent.kitting_no == K1)).one().id}


def _end(client, event_id, end_at="2026-10-10T11:00:00+09:00", **body):
    body = {"reason": "forgot", **body}
    return client.post(f"/api/admin/open-runs/{event_id}/end", json={"end_at": end_at, **body}, headers=H)


def test_list_has_only_old_open_records(client, old_runs):
    rows = ok(client.get("/api/admin/open-runs"))
    assert [(r["id"], r["kitting_no"], r["step_type"], r["line_code"]) for r in rows] == [(old_runs["old"], K1, "setup", "S")]
    assert ok(client.get("/api/admin/open-runs", params={"line_code": "S"}))[0]["id"] == old_runs["old"]
    assert ok(client.get("/api/admin/open-runs", params={"line_code": "T"})) == []  # ラインで絞り込める
    board = ok(client.get("/api/lines/S/board"))
    assert board["stale_kitting_nos"] == [K1]  # ライン画面の警告と同じ定義


def test_list_needs_admin_login(client, staffed):
    client.cookies.clear()
    assert client.get("/api/admin/open-runs").status_code == 401


def test_end_records_correction_and_audit(client, old_runs):
    r = ok(_end(client, old_runs["old"]))
    assert (r["action"], r["completed"]) == ("end", False)
    with new_session() as s:
        e = s.get(RunEvent, old_runs["old"])
        assert e.end_at == datetime(2026, 10, 10, 11, 0, tzinfo=JST) and e.ended_by is not None
        c = s.scalars(select(RunCorrection).where(RunCorrection.target_id == e.id)).one()
        assert (c.source, c.kind, c.reason, c.corrected_by) == ("admin", "update", "forgot", e.ended_by)
        a = s.scalars(select(AuditLog).where(AuditLog.target_table == "run_events", AuditLog.target_key == str(e.id))).one()
        assert (a.action, a.changed_by, a.reason) == ("admin_end_open_run", e.ended_by, "forgot")
    assert ok(client.get("/api/admin/open-runs")) == []
    assert ok(client.get("/api/lines/S/board"))["stale_kitting_nos"] == []  # 警告が消える


@pytest.mark.parametrize("end_at, msg", [
    ("2026-10-10T09:00:00+09:00", "開始の時刻は、終了の時刻より前"),  # 開始より前
    ("2026-10-22T09:00:00+09:00", "未来の時刻"),  # 今より後
])
def test_end_time_checks(client, old_runs, end_at, msg):
    r = _end(client, old_runs["old"], end_at=end_at)
    assert r.status_code == 409 and msg in r.json()["detail"]
    with new_session() as s:
        assert s.get(RunEvent, old_runs["old"]).end_at is None and s.scalars(select(RunCorrection)).first() is None


def test_end_checks_reason_and_qty(client, old_runs):
    assert _end(client, old_runs["old"], reason="other").status_code == 409  # その他は記入が要る
    assert _end(client, old_runs["old"], produced_qty=5).status_code == 409  # 段取りに良品数はない


def test_end_rejects_record_in_field_range(client, old_runs):
    with new_session() as s:
        recent = s.scalars(select(RunEvent).where(RunEvent.kitting_no == K2)).one().id
    r = _end(client, recent, end_at="2026-10-21T07:59:00+09:00")
    assert r.status_code == 409 and "対象ではありません" in r.json()["detail"]
    assert client.post("/api/admin/open-runs/9999/void", json={"reason": "mistake"}, headers=H).status_code == 404


def test_void_marks_and_records(client, old_runs):
    r = ok(client.post(f"/api/admin/open-runs/{old_runs['old']}/void", json={"reason": "mistake"}, headers=H))
    assert r["action"] == "void"
    with new_session() as s:
        e = s.get(RunEvent, old_runs["old"])
        assert e.voided_at is not None and e.voided_by is not None and e.void_reason == "mistake"  # 行は残る
        c = s.scalars(select(RunCorrection).where(RunCorrection.target_id == e.id)).one()
        assert (c.source, c.kind) == ("admin", "void")
        assert s.scalars(select(AuditLog).where(AuditLog.action == "admin_void_open_run")).one().changed_by == e.voided_by
    assert ok(client.get("/api/admin/open-runs")) == []
    assert client.post(f"/api/admin/open-runs/{old_runs['old']}/void", json={"reason": "mistake"}, headers=H).status_code == 409  # 2回目


def test_ending_open_cleanup_completes_plan(client, staffed, fake_clock):
    now = fake_clock.current
    fake_clock.current = OLD
    ok(start(client, "cleanup", kitting_no=K1))
    fake_clock.current = now
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", PASSWORD)
    assert login(client).status_code == 200
    with new_session() as s:
        eid = s.scalars(select(RunEvent)).one().id
    r = ok(_end(client, eid, end_at="2026-10-10T10:30:00+09:00"))
    assert r["completed"] is True  # 現場で片付けを終えたときと同じ完了の写し
    with new_session() as s:
        comp = s.scalars(select(RunCompletion)).one()
        assert (comp.kitting_no, comp.cleanup_event_id, comp.kind) == (K1, eid, "cleanup")
        assert comp.completed_at == datetime(2026, 10, 10, 10, 30, tzinfo=JST)


def test_demo_seed_stale_open(client, fake_clock):
    from datetime import date

    from app.services.demo_seed import seed_stale_open

    with new_session() as s:
        ids = seed_stale_open(s, "S", date(2026, 10, 21))
    assert len(ids) == 2
    board = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert len(board["stale_kitting_nos"]) == 2  # 10日前に始めて終了していない記録(表示範囲を広げても入らない)
