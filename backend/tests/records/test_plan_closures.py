"""計画終了(始まっていない計画を手で終わらせる)と、その取り消し(AD-24)。作業者ID・理由・履歴・audit_log・工程の拒否・同期で消えないこと。"""

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, Plan, PlanClosure
from app.services import masters
from records_helpers import K1, K2, add, at, conflict, new_session, ok, start, sync_plans


@pytest.fixture
def worker(staffed):
    with new_session() as s:
        masters.add_operator(s, "鈴木", worker_id="Z001")
    return "Z001"


def close(client, kno=K1, worker_id="Z001", reason="plan_change", note=None, request_id=None):
    return client.post(f"/api/runs/{kno}/close", json={
        "request_id": request_id or f"close-{kno}-{reason}", "worker_id": worker_id, "reason": reason, "note": note})


def cancel(client, kno=K1, worker_id="Z001", request_id=None):
    return client.post(f"/api/runs/{kno}/close/cancel", json={"request_id": request_id or f"cancel-{kno}", "worker_id": worker_id})


def board_plan(client, kno=K1):
    return next(p for p in ok(client.get("/api/lines/S/board"))["plans"] if p["plan"]["kitting_no"] == kno)


def test_close_records_history_and_audit(client, worker):
    r = ok(close(client, reason="delay_stop"))
    assert r["closed"] is True and r["closure"]["reason"] == "delay_stop" and r["closure"]["closed_by_name"] == "鈴木"
    plan = board_plan(client)
    assert plan["closed"]["reason"] == "delay_stop" and plan["completed"] is False  # 完了とは別の扱い
    with new_session() as s:
        rows = s.scalars(select(PlanClosure)).all()
        assert [(x.kitting_no, x.action, x.reason) for x in rows] == [(K1, "close", "delay_stop")]
        a = s.scalars(select(AuditLog).where(AuditLog.target_table == "plan_closures")).one()
        assert (a.action, a.target_key, a.reason) == ("plan_close", K1, "delay_stop")


def test_close_is_idempotent_and_not_repeated(client, worker):
    first = ok(close(client))
    assert ok(close(client)) == first  # 同じ request_id の再送
    conflict(close(client, request_id="another"), "すでに計画終了")
    with new_session() as s:
        assert len(s.scalars(select(PlanClosure)).all()) == 1


def test_close_checks_inputs(client, worker):
    conflict(close(client, reason="other"), "内容を記入")
    conflict(close(client, reason="other", note="  "), "内容を記入")
    ok(close(client, reason="other", note="客先の都合"))
    conflict(close(client, kno=K2, reason="nope"), "理由を選んで")
    assert close(client, kno=K2, worker_id="Q999").status_code == 404  # 作業者IDが見つからない
    assert client.post(f"/api/runs/{K2}/close", json={"request_id": "x", "reason": "plan_change"}).status_code == 422  # 作業者IDは必須


def test_started_plan_cannot_be_closed(client, worker):
    ok(start(client, "setup"))
    conflict(close(client), "作業が始まっている")


def test_cancelled_plan_cannot_be_closed(client, worker):
    with new_session() as s:
        for p in s.scalars(select(Plan).where(Plan.kitting_no == K1)):
            p.status = "cancelled"
        s.commit()
    conflict(close(client), "取消になった計画")


def test_closed_plan_rejects_steps_until_cancelled(client, worker):
    ok(close(client))
    conflict(start(client, "setup"), "先に「計画終了を取り消す」")
    conflict(add(client, "setup", at("08:00"), at("08:01")), "先に「計画終了を取り消す」")
    ok(start(client, "setup", kitting_no=K2))  # ほかの計画は始められる
    ok(cancel(client))
    assert board_plan(client)["closed"] is None
    ok(start(client, "setup"))
    with new_session() as s:
        assert [x.action for x in s.scalars(select(PlanClosure).where(PlanClosure.kitting_no == K1).order_by(PlanClosure.id))] == ["close", "cancel"]
        assert s.scalars(select(AuditLog).where(AuditLog.action == "plan_close_cancel")).one().target_key == K1  # 履歴は足すだけ


def test_cancel_needs_closed_plan_and_worker(client, worker):
    conflict(cancel(client), "計画終了していません")
    ok(close(client))
    assert cancel(client, worker_id="Q999").status_code == 404
    assert client.post(f"/api/runs/{K1}/close/cancel", json={"request_id": "y"}).status_code == 422


def test_closure_survives_plan_sync(client, world, worker):
    ok(close(client))
    sync_plans(world["app"])
    sync_plans(world["app"])  # 取り込み直しでも消えない(plans とは別の表)
    assert board_plan(client)["closed"] is not None


def test_search_result_has_closure(client, worker):
    ok(close(client))
    assert ok(client.get(f"/api/runs/{K1}"))["closed"]["reason"] == "plan_change"  # 検索で選んだ計画(範囲の外でも)
