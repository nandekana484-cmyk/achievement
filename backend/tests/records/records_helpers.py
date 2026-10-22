"""実績のAPIのテストで使う定数と関数。"""

import uuid

from sqlalchemy import func, select

from app.db.models import Reason
from app.db.session import get_sessionmaker
from app.services.plan_sync import run_plan_sync

K1 = "0722-1-S-251014-01"
K2 = "0722-2-S-251014-02"


def rid() -> str:
    return uuid.uuid4().hex


def new_session():
    return get_sessionmaker()()


def sync_plans(legacy_app):
    with new_session() as s:
        r = run_plan_sync(s, legacy_app)
    assert r.result == "ok"
    return r


def count_rows(model, **where) -> int:
    with new_session() as s:
        stmt = select(func.count()).select_from(model)
        for k, v in where.items():
            stmt = stmt.where(getattr(model, k) == v)
        return s.scalar(stmt)


def reason_id(name: str) -> int:
    with new_session() as s:
        return s.scalars(select(Reason.id).where(Reason.name == name)).one()


def set_operator(client, operator_id, line="S"):
    r = client.put(f"/api/lines/{line}/operator", json={"request_id": rid(), "operator_id": operator_id})
    assert r.status_code == 200, r.text
    return r.json()


def start(client, step, kitting_no=K1, **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/runs/{kitting_no}/steps/{step}/start", json=body)


def end(client, step, kitting_no=K1, **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/runs/{kitting_no}/steps/{step}/end", json=body)


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def conflict(r, text):
    assert r.status_code == 409, r.text
    assert text in r.json()["detail"]
    return r.json()["detail"]


def ev_start(client, line="S", **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/lines/{line}/events/start", json=body)


def ev_end(client, event_id, line="S", **body):
    body.setdefault("request_id", rid())
    return client.post(f"/api/lines/{line}/events/{event_id}/end", json=body)


def at(hm: str, day: int = 21) -> str:
    """2026-10-<day> の日本時間の時刻(訂正で送る形)。"""
    return f"2026-10-{day:02d}T{hm}:00+09:00"


def fix(client, event_id, kitting_no=K1, **body):
    """工程の記録の訂正(理由の既定は押し間違い)。"""
    body.setdefault("request_id", rid())
    body.setdefault("reason", "mistake")
    return client.patch(f"/api/runs/{kitting_no}/events/{event_id}", json=body)


def void(client, event_id, kitting_no=K1, **body):
    body.setdefault("request_id", rid())
    body.setdefault("reason", "mistake")
    return client.post(f"/api/runs/{kitting_no}/events/{event_id}/void", json=body)


def add(client, step, start_at, end_at, kitting_no=K1, **body):
    body.setdefault("request_id", rid())
    body.setdefault("reason", "forgot")
    return client.post(f"/api/runs/{kitting_no}/events", json={"step_type": step, "start_at": start_at, "end_at": end_at, **body})


def history(client, kitting_no=K1):
    return ok(client.get(f"/api/runs/{kitting_no}/corrections"))


def board_plan(client, kitting_no=K1, date="2026-10-21"):
    plans = ok(client.get("/api/lines/S/board", params={"date": date}))["plans"]
    return next(p for p in plans if p["plan"]["kitting_no"] == kitting_no)
