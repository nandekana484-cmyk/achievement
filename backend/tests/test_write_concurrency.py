"""書き込みの衝突の防止(開発指針 9)。

- 本アプリのDBへの書き込みは BEGIN IMMEDIATE で始め、同じプロセス内では1つのロックで1つずつ行う
- ボタン操作と計画の同期を複数のスレッドで同時に動かしても、500 が出ず、記録が欠けたり重複したりしない
- それでもロックが取れなかったときは 503。api_requests には記録せず、同じ request_id で送り直せば記録される
"""

import sqlite3
import threading
import time
import uuid
from collections import Counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text

from app.db import session as db_session
from app.db.models import (
    ApiRequest,
    LineEvent,
    LineOperator,
    Operator,
    Plan,
    PlanSyncRun,
    Reason,
    RunCompletion,
    RunEvent,
    RunInput,
)
from app.db.session import get_sessionmaker, make_engine, write_transaction
from app.services import masters
from app.services.errors import Busy
from app.services.plan_sync import run_plan_sync
from legacy_fixture import insert_plan

BUSY_MESSAGE = "他の処理と重なったため、記録できませんでした。もう一度押してください"


def rid() -> str:
    return uuid.uuid4().hex


def _client(tmp_path, monkeypatch) -> TestClient:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "api.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    return TestClient(app)


def _count(model, *where) -> int:
    with get_sessionmaker()() as s:
        return s.scalar(select(func.count()).select_from(model).where(*where))


def _reason_id(name: str) -> int:
    with get_sessionmaker()() as s:
        return s.scalars(select(Reason.id).where(Reason.name == name)).one()


# --- BEGIN IMMEDIATE ---


def test_write_transaction_begins_immediate(tmp_path):
    engine = make_engine(tmp_path / "t.db")
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda _c, _cur, stmt, *_: statements.append(stmt))
    from sqlalchemy.orm import Session

    with engine.begin() as c:
        c.execute(text("CREATE TABLE t (v INTEGER)"))
    statements.clear()

    with Session(engine) as s:
        s.execute(text("SELECT count(*) FROM t"))  # 読み取りは普通の BEGIN
        with write_transaction(s):  # 読み取りの途中なら、いったん終えてから書き込みのロックを取る
            s.execute(text("INSERT INTO t VALUES (1)"))
            s.commit()

    assert [x for x in statements if x.startswith("BEGIN")] == ["BEGIN", "BEGIN IMMEDIATE"]
    engine.dispose()


# --- 同時実行 ---

N_PLANS = 8  # 計画ごとにスレッド1本(工程・NG数・備考を操作)
N_LINE_EVENT_THREADS = 2  # 付帯作業(理由ごとにスレッド1本)
N_LINE_EVENT_CYCLES = 10
N_OPERATOR_CHANGES = 10
N_SYNCS = 15
SENDS = 2  # 同じ request_id で2回ずつ送る(再送)


def _plan_kno(i: int) -> str:
    return f"{700 + i:04d}-1-S-251014-{i:02d}"


def test_concurrent_button_operations_and_sync(tmp_path, monkeypatch, legacy_app, legacy_db, fake_clock, capsys):
    for i in range(N_PLANS):
        insert_plan(legacy_db, kitting_no=_plan_kno(i), file_no=f"{700 + i:04d}", lot_no=f"L{i:03d}")
    sync_target = "0799-1-S-251014-99"  # 同期のたびに数量を変える計画(同期にも書き込ませる)
    insert_plan(legacy_db, kitting_no=sync_target, file_no="0799", lot_no="L999", qty=100)

    with _client(tmp_path, monkeypatch) as client:
        with get_sessionmaker()() as s:
            assert run_plan_sync(s, legacy_app).result == "ok"
            yamada = masters.add_operator(s, "山田").id
            sato = masters.add_operator(s, "佐藤").id
        client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": yamada})
        restart = [_reason_id("人員交代"), _reason_id("トラブル停止")]
        line_reasons = [_reason_id("部品探し"), _reason_id("欠品")]

        statuses: Counter = Counter()
        failures: list[str] = []
        sync_results: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(N_PLANS + N_LINE_EVENT_THREADS + 2)

        def send(method: str, url: str, body: dict) -> dict:
            body = {"request_id": rid(), **body}
            first = None
            for _ in range(SENDS):
                r = client.request(method, url, json=body)
                with lock:
                    statuses[r.status_code] += 1
                    if r.status_code != 200:
                        failures.append(f"{method} {url} -> {r.status_code} {r.text}")
                if first is None:
                    first = r.json()
                elif r.status_code == 200 and r.json() != first:
                    with lock:
                        failures.append(f"再送で応答が変わった: {url}")
            return first

        def plan_worker(i: int) -> None:
            base = f"/api/runs/{_plan_kno(i)}/L{i:03d}"
            barrier.wait()
            op = {"operator_id": yamada}
            send("POST", f"{base}/steps/setup/start", op)
            send("POST", f"{base}/steps/setup/end", op)
            for seg in range(3):
                send("POST", f"{base}/steps/production/start", {**op, "restart_reason_id": restart[seg - 1] if seg else None})
                send("POST", f"{base}/steps/production/end", {**op, "produced_qty": 10 * (seg + 1)})
            send("PUT", f"{base}/ng-qty", {**op, "ng_qty": i})
            send("POST", f"{base}/remarks", {**op, "text": f"備考{i}"})
            send("POST", f"{base}/steps/cleanup/start", op)
            send("POST", f"{base}/steps/cleanup/end", op)

        def line_event_worker(reason_id: int) -> None:
            barrier.wait()
            for _ in range(N_LINE_EVENT_CYCLES):
                e = send("POST", "/api/lines/S/events/start", {"reason_id": reason_id, "operator_id": sato})
                send("POST", f"/api/lines/S/events/{e['id']}/end", {"operator_id": sato})

        def operator_worker() -> None:
            barrier.wait()
            for n in range(N_OPERATOR_CHANGES):
                send("PUT", "/api/lines/S/operator", {"operator_id": sato if n % 2 == 0 else yamada})

        def sync_worker() -> None:
            barrier.wait()
            for n in range(N_SYNCS):
                insert_plan(legacy_db, kitting_no=sync_target, file_no="0799", lot_no="L999", qty=101 + n)
                with get_sessionmaker()() as s:
                    r = run_plan_sync(s, legacy_app)
                with lock:
                    sync_results.append(r.result if r.result == "ok" else f"{r.result}: {r.error_message}")

        threads = [threading.Thread(target=plan_worker, args=(i,)) for i in range(N_PLANS)]
        threads += [threading.Thread(target=line_event_worker, args=(r,)) for r in line_reasons]
        threads += [threading.Thread(target=operator_worker), threading.Thread(target=sync_worker)]
        started = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        elapsed = time.perf_counter() - started

        assert not any(t.is_alive() for t in threads), "終わらないスレッドがあります"
        assert failures == []
        assert set(statuses) == {200}  # 500 も 503 も出ない
        assert sync_results == ["ok"] * N_SYNCS

        # 記録が欠けたり重複したりしていない
        assert _count(RunEvent) == N_PLANS * 5
        assert _count(RunEvent, RunEvent.end_at.is_(None)) == 0
        assert _count(RunCompletion) == N_PLANS
        assert _count(RunInput) == N_PLANS * 2
        assert _count(LineEvent) == N_LINE_EVENT_THREADS * N_LINE_EVENT_CYCLES
        assert _count(LineEvent, LineEvent.end_at.is_(None)) == 0
        assert _count(LineOperator) == 1 + N_OPERATOR_CHANGES
        assert _count(LineOperator, LineOperator.end_at.is_(None)) == 1
        assert _count(PlanSyncRun) == 1 + N_SYNCS
        with get_sessionmaker()() as s:
            for i in range(N_PLANS):
                seqs = list(s.scalars(select(RunEvent.seq).where(
                    RunEvent.kitting_no == _plan_kno(i), RunEvent.step_type == "production").order_by(RunEvent.seq)))
                assert seqs == [1, 2, 3]
                c = s.scalars(select(RunCompletion).where(RunCompletion.kitting_no == _plan_kno(i))).one()
                assert (c.produced_qty, c.ng_qty) == (60, i)
            assert s.get(Plan, (sync_target, "L999")).planned_qty == 100 + N_SYNCS

        operations = sum(statuses.values()) // SENDS
        assert _count(ApiRequest) == 1 + operations  # 最初の担当者の設定 + 各操作(再送は数えない)
        with capsys.disabled():
            print(
                f"\n[同時実行] スレッド {len(threads)}本(計画 {N_PLANS}・付帯作業 {N_LINE_EVENT_THREADS}・"
                f"担当者の交代 1・計画の同期 1)、ボタン操作 {operations}回(再送込みのリクエスト "
                f"{sum(statuses.values())}回)、計画の同期 {N_SYNCS}回、{elapsed:.2f}秒"
            )


# --- ロックの取り合い ---


@pytest.fixture
def short_busy_timeout(monkeypatch):
    monkeypatch.setattr(db_session, "BUSY_TIMEOUT_MS", 200)


def _hold_write_lock(db_path):
    """ほかのプロセス(手で動かした Alembic など)が書き込みのロックを持っている状態を作る。"""
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=1)
    conn.execute("BEGIN IMMEDIATE")
    return conn


def test_lock_contention_returns_503_and_resend_records(tmp_path, monkeypatch, short_busy_timeout, legacy_app, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    with _client(tmp_path, monkeypatch) as client:
        with get_sessionmaker()() as s:
            run_plan_sync(s, legacy_app)
            op = masters.add_operator(s, "山田").id
        body = {"request_id": rid(), "operator_id": op}
        url = "/api/runs/0722-1-S-251014-01/L001/steps/setup/start"

        holder = _hold_write_lock(tmp_path / "api.db")
        try:
            r = client.post(url, json=body)
            assert r.status_code == 503
            assert r.json() == {"detail": BUSY_MESSAGE}
            r = client.put("/api/lines/S/operator", json={"request_id": rid(), "operator_id": op})
            assert r.status_code == 503  # 担当者の交代も同じ
        finally:
            holder.rollback()
            holder.close()

        assert _count(ApiRequest) == 0 and _count(RunEvent) == 0  # 記録しない
        r = client.post(url, json=body)  # 同じ request_id で送り直すと記録される
        assert r.status_code == 200
        assert _count(ApiRequest) == 1 and _count(RunEvent) == 1
        assert client.post(url, json=body).json() == r.json()


def test_sync_under_lock_contention_does_not_raise(tmp_path, short_busy_timeout, session_factory, engine, legacy_app, legacy_db, fake_clock):
    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    db_path = engine.url.database
    holder = _hold_write_lock(db_path)
    try:
        engine.dispose()  # 短い待ち時間で接続し直す
        with session_factory() as s:
            r = run_plan_sync(s, legacy_app)
    finally:
        holder.rollback()
        holder.close()

    assert r.result == "error" and r.sync_run_id is None  # 失敗の記録もできなかったが、例外にはしない
    with session_factory() as s:
        assert run_plan_sync(s, legacy_app).result == "ok"  # 次の回で反映される
        assert s.scalar(select(func.count()).select_from(Plan)) == 1


def test_busy_error_in_service_is_not_recorded(session_factory, legacy_app, legacy_db, fake_clock, monkeypatch, tmp_path, short_busy_timeout, engine):
    from app.domain.steps import StepType
    from app.services import run_records

    insert_plan(legacy_db, kitting_no="0722-1-S-251014-01")
    with session_factory() as s:
        run_plan_sync(s, legacy_app)
        op = masters.add_operator(s, "山田").id
    engine.dispose()
    holder = _hold_write_lock(engine.url.database)
    try:
        with session_factory() as s, pytest.raises(Busy):
            run_records.start_step(s, "0722-1-S-251014-01", "L001", StepType.SETUP, "same-id", operator_id=op)
    finally:
        holder.rollback()
        holder.close()
    with session_factory() as s:
        run_records.start_step(s, "0722-1-S-251014-01", "L001", StepType.SETUP, "same-id", operator_id=op)
        assert s.scalar(select(func.count()).select_from(RunEvent)) == 1
        assert s.scalar(select(func.count()).select_from(Operator)) == 1
