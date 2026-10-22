"""集計: 区間(稼働日をまたぐ記録、取り消し、作業中)、区間の CSV、日報(開発指針 7.2)。"""

import csv
import io

import pytest

from app.services import admin_auth, masters
from records_helpers import K1, K2, end, ev_end, ev_start, new_session, ok, reason_id, rid, start, void

H = {"X-Genba-Admin": "1"}
CSV_URL = "/api/admin/reports/intervals.csv"


def login(client):
    """管理者でログインする(テストの時計を進めるとログインが切れるので、集計を読む直前に呼ぶ)。"""
    r = client.post("/api/admin/login", json={"worker_id": "K0042", "password": "right-pass-1"}, headers=H)
    assert r.status_code == 200


@pytest.fixture
def admin(client, staffed):
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", "right-pass-1")
    login(client)
    return staffed


@pytest.fixture
def records(client, admin, fake_clock):
    """今(10/21 8:00 = 稼働日 10/20)から: K1 の生産 8:00〜8:30(100枚。8:15 をまたぐ)、取り消した段取り、
    部品探し 8:30〜8:50、K2 の段取り 8:50〜(終了していない)。最後に時計は 9:00。"""
    ok(start(client, "production"))
    fake_clock.advance(minutes=30)
    ok(end(client, "production", produced_qty=100))
    mistaken = ok(start(client, "setup"))["event"]
    ok(void(client, mistaken["id"]))
    e = ok(ev_start(client, reason_id=reason_id("部品探し")))
    fake_clock.advance(minutes=20)
    ok(ev_end(client, e["id"]))
    ok(start(client, "setup", kitting_no=K2))
    fake_clock.advance(minutes=10)
    login(client)
    return admin


def _csv(client, **params):
    r = client.get(CSV_URL, params=params)
    assert r.status_code == 200, r.text
    text = r.content.decode("utf-8-sig")
    return r, list(csv.DictReader(io.StringIO(text, newline="")))


def test_intervals_split_at_workday_and_skip_voided(client, records):
    _, rows = _csv(client, **{"from": "2026-10-20", "to": "2026-10-21"})
    got = [(r["稼働日"], r["区分"], r["キッティングNo."], r["工程または理由"], r["開始(この稼働日)"][11:16],
            r["終了(この稼働日)"][11:16], r["時間(分)"], r["生産数"], r["作業中"]) for r in rows]
    assert got == [
        ("2026-10-20", "工程", K1, "生産", "08:00", "08:15", "15.0", "", ""),
        ("2026-10-21", "工程", K1, "生産", "08:15", "08:30", "15.0", "100", ""),  # 生産数は終了を含む区間に付ける
        ("2026-10-21", "付帯作業", "", "部品探し", "08:30", "08:50", "20.0", "", ""),
        ("2026-10-21", "工程", K2, "段取り", "08:50", "", "10.0", "", "○"),  # 終了していない: 出力した時刻(9:00)まで
    ]
    first = rows[0]
    assert (first["元の開始"], first["元の終了"]) == ("2026-10-21 08:00:00", "2026-10-21 08:30:00")
    assert (first["ライン"], first["ロットNo."], first["ファイルNo."], first["品名"], first["回"]) == ("S", "L001", "0722", "基板A", "1")
    assert (first["開始した人"], first["終了した人"], first["後から追加"], first["訂正あり"]) == ("山田", "山田", "", "")
    assert rows[3]["元の終了"] == "" and rows[3]["終了した人"] == ""


def test_corrected_and_added_flags(client, records, fake_clock):
    r = client.post(f"/api/runs/{K1}/events", json={"request_id": rid(), "reason": "forgot", "step_type": "cleanup",
                                                     "start_at": "2026-10-21T08:40:00+09:00", "end_at": "2026-10-21T08:45:00+09:00"})
    ok(r)
    _, rows = _csv(client, **{"from": "2026-10-21", "to": "2026-10-21"})
    cleanup = next(x for x in rows if x["工程または理由"] == "片付け")
    assert (cleanup["後から追加"], cleanup["訂正あり"]) == ("○", "○")


def test_csv_format(client, records):
    r, _ = _csv(client, **{"from": "2026-10-21", "to": "2026-10-21", "line_code": "s"})
    assert r.content.startswith(b"\xef\xbb\xbf")  # BOM
    body = r.content[3:]
    assert body.count(b"\r\n") == body.count(b"\n") and body.endswith(b"\r\n")  # 改行はすべて CRLF
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="intervals_2026-10-21_2026-10-21_S.csv"' in r.headers["content-disposition"]
    header = body.decode("utf-8").split("\r\n")[0].split(",")
    assert header[:4] == ["稼働日", "ライン", "区分", "キッティングNo."] and "時間(分)" in header and "訂正あり" in header
    r2, _ = _csv(client, **{"from": "2026-10-21", "to": "2026-10-21"})
    assert "intervals_2026-10-21_2026-10-21_all.csv" in r2.headers["content-disposition"]


def test_csv_filters_period_and_line(client, records):
    _, rows = _csv(client, **{"from": "2026-10-20", "to": "2026-10-20"})
    assert [r["稼働日"] for r in rows] == ["2026-10-20"]
    with new_session() as s:
        from app.db.models import Line

        s.add(Line(line_code="T", name="Tライン", active=True, sort_order=99))
        s.commit()
    _, rows = _csv(client, **{"from": "2026-10-20", "to": "2026-10-21", "line_code": "T"})
    assert rows == []
    assert client.get(CSV_URL, params={"from": "2026-10-20", "to": "2026-10-21", "line_code": "ZZ"}).status_code == 404


def test_csv_period_limit(client, admin):
    r = client.get(CSV_URL, params={"from": "2026-01-01", "to": "2026-04-03"})  # 93日
    assert r.status_code == 200
    r = client.get(CSV_URL, params={"from": "2026-01-01", "to": "2026-04-04"})  # 94日
    assert r.status_code == 409 and "93 日まで" in r.json()["detail"]
    r = client.get(CSV_URL, params={"from": "2026-01-02", "to": "2026-01-01"})
    assert r.status_code == 409


def test_reports_require_login(client, staffed):
    assert client.get(CSV_URL, params={"from": "2026-10-21", "to": "2026-10-21"}).status_code == 401
    assert client.get("/api/admin/reports/daily", params={"date": "2026-10-21", "line_code": "S"}).status_code == 401


def test_daily_report_rows_totals_and_halves(client, records, fake_clock):
    ok(client.put(f"/api/runs/{K1}/ng-qty", json={"request_id": rid(), "lot_no": "L001", "side": 1, "ng_qty": 3}))
    fake_clock.advance(hours=12)  # 21:00(下段)
    ok(start(client, "first_article"))
    fake_clock.advance(minutes=10)
    ok(end(client, "first_article"))
    login(client)

    d = ok(client.get("/api/admin/reports/daily", params={"date": "2026-10-21", "line_code": "S"}))

    assert (d["produced_total"], d["ng_total"]) == (100, 3)
    assert [(h["start"], h["end"]) for h in d["halves"]] == [
        ("2026-10-21T08:15:00+09:00", "2026-10-21T20:15:00+09:00"), ("2026-10-21T20:15:00+09:00", "2026-10-22T08:15:00+09:00"),
    ]
    assert d["generated_at"] == "2026-10-21T21:10:00+09:00"
    assert [(r["kind"], r["kitting_no"]) for r in d["rows"]] == [("step", K1), ("step", K2), ("line_event", None)]
    k1, k2, events = d["rows"]
    assert [(b["half"], b["step_type"], b["start"][11:16], b["end"][11:16]) for b in k1["bars"]] == [
        (0, "production", "08:15", "08:30"), (1, "first_article", "21:00", "21:10"),
    ]
    # 終了していない段取りは今まで。上段と下段に分ける
    assert [(b["half"], b["start"][11:16], b["end"][11:16], b["open"]) for b in k2["bars"]] == [
        (0, "08:50", "20:15", True), (1, "20:15", "21:10", True),
    ]
    assert [(b["label"], b["half"]) for b in events["bars"]] == [("部品探し", 0)]
    assert k1["product_names"] == "基板A"


def test_daily_report_empty_day_and_unknown_line(client, admin):
    d = ok(client.get("/api/admin/reports/daily", params={"date": "2026-10-25", "line_code": "S"}))
    assert (d["rows"], d["produced_total"], d["ng_total"]) == ([], 0, 0)
    assert client.get("/api/admin/reports/daily", params={"date": "2026-10-25", "line_code": "ZZ"}).status_code == 404
