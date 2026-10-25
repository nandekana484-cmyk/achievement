"""実績の書き出しのテストの補助(管理者・生産・片付け・NG・一覧)。"""

import pytest

from app.core.config import get_config
from app.services import admin_auth, masters
from records_helpers import end, new_session, ok, reason_id, rid, set_operator, start

H = {"X-Genba-Admin": "1"}
URL = "/api/admin/actuals"
DAY = {"from": "2026-10-21", "to": "2026-10-21"}
BODY = {"date_from": "2026-10-21", "date_to": "2026-10-21"}
K3 = "0800-1-S-251014-03"  # 面1だけ(面2の計画が無い)
K4 = "0900-1-S-251014-04"  # 面1・2ロット(A 100、B 50)


def login(client):
    r = client.post("/api/admin/login", json={"worker_id": "K0042", "password": "right-pass-1"}, headers=H)
    assert r.status_code == 200


@pytest.fixture
def admin(client, world, tmp_path, fake_clock):
    """管理者 K0042、今の担当者は作業者ID Y100 の鈴木。書き出し先は tmp_path/exchange。時計は 10/21 9:00(稼働日 10/21)。"""
    cfg = tmp_path / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + f'exchange_dir = "{(tmp_path / "exchange").as_posix()}"\n', encoding="utf-8")
    get_config.cache_clear()
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", "right-pass-1")
        suzuki = masters.add_operator(s, "鈴木", worker_id="Y100").id
    set_operator(client, suzuki)
    fake_clock.advance(hours=1)
    return {**world, "suzuki": suzuki, "exchange": tmp_path / "exchange"}


def produce(client, fake_clock, kitting_no, *qtys):
    for i, q in enumerate(qtys):
        extra = {"restart_reason_id": reason_id("人員交代")} if i else {}
        ok(start(client, "production", kitting_no=kitting_no, **extra))
        fake_clock.advance(minutes=10)
        ok(end(client, "production", kitting_no=kitting_no, produced_qty=q))


def finish(client, fake_clock, kitting_no):
    ok(start(client, "cleanup", kitting_no=kitting_no))
    fake_clock.advance(minutes=5)
    ok(end(client, "cleanup", kitting_no=kitting_no))


def ng(client, kitting_no, lot_no, side, qty):
    ok(client.put(f"/api/runs/{kitting_no}/ng-qty", json={"request_id": rid(), "lot_no": lot_no, "side": side, "ng_qty": qty}))


def listing(client, **params):
    login(client)
    r = client.get(URL, params={**DAY, **params})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def by_key(rows):
    return {(r["kitting_no"], r["lot_no"]): r for r in rows}


def export(client, **body):
    login(client)
    return client.post(f"{URL}/export", json={**BODY, **body}, headers=H)
