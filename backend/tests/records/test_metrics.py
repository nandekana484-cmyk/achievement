"""効率と進捗率(docs/design/metrics.md)。画面のバー・日報・区間の CSV が同じ値になること。"""

import csv
import io

import pytest

from app.services import admin_auth, masters
from legacy_fixture import insert_plan, put_teitori, set_takt
from records_helpers import K1, K2, board_plan, end, ev_end, ev_start, new_session, ok, reason_id, start, sync_plans, void

H = {"X-Genba-Admin": "1"}
DAY = "2026-10-21"
LOGIN = {"worker_id": "K0042", "password": "right-pass-1"}


def board(client, date=DAY):
    return ok(client.get("/api/lines/S/board", params={"date": date}))


def eff(client, date=DAY):
    return board(client, date)["efficiency"]


def setup_master(world, takt="60", teitori=4):
    """K1(0722 / S / 面1)の目標タクトと丁取り数を決めて、同期し直す。"""
    master = world["app"] / "db" / "master.db"
    set_takt(master, "0722", "S", "1", takt)
    put_teitori(master, "0722", "S", teitori)
    sync_plans(world["app"])
    return master


def run_production(client, fake_clock, minutes, qty, kitting_no=K1):
    ok(start(client, "production", kitting_no=kitting_no))
    fake_clock.advance(minutes=minutes)
    ok(end(client, "production", kitting_no=kitting_no, produced_qty=qty))


@pytest.fixture
def at_nine(fake_clock):
    fake_clock.advance(minutes=60)  # 9:00(稼働日 10/21)


def test_spec_example_is_80_percent(client, staffed, fake_clock, at_nine):
    setup_master(staffed)  # 目標タクト60秒、4丁取り
    run_production(client, fake_clock, 150, 480)  # 良品480台 = 120枚 × 60秒 = 2時間。実所要2時間30分
    e = eff(client)
    assert e["efficiency"] == pytest.approx(0.8)
    assert (e["standard_seconds"], e["actual_seconds"], e["included"], e["excluded"]) == (7200, 9000, 1, 0)


@pytest.mark.parametrize(("teitori", "expected"), [(1, 3.2), (4, 0.8)])
def test_efficiency_scales_with_teitori(client, staffed, fake_clock, at_nine, teitori, expected):
    setup_master(staffed, teitori=teitori)
    run_production(client, fake_clock, 150, 480)
    assert eff(client)["efficiency"] == pytest.approx(expected)  # 丁取り1と4で同じ時間なら4倍違う


def test_pieces_are_not_rounded_up(client, staffed, fake_clock, at_nine):
    setup_master(staffed, teitori=4)
    run_production(client, fake_clock, 60, 10)  # 10台 ÷ 4丁取り = 2.5枚(切り上げない)
    assert eff(client)["standard_seconds"] == pytest.approx(150)


@pytest.mark.parametrize("status", ["tsv_not_found", "ambiguous_tsv", "read_error", "no_k_row", "multi_k",
                                    "code_not_in_master", "teitori_invalid", "a_status_we_do_not_know"])
def test_plan_without_teitori_is_excluded(client, staffed, fake_clock, at_nine, status):
    master = setup_master(staffed)
    put_teitori(master, "0722", "S", 3 if status == "a_status_we_do_not_know" else None, status)  # 知らない status は丁取り数があっても使わない
    sync_plans(staffed["app"])
    run_production(client, fake_clock, 60, 100)
    e = eff(client)
    assert (e["efficiency"], e["included"], e["excluded"]) == (None, 0, 1)
    assert e["reasons"] == [{"reason": status, "count": 1}]
    assert e["excluded_plans"] == [{"kitting_no": K1, "reason": status}]


def test_excluded_plans_leave_both_numerator_and_denominator(client, staffed, fake_clock, at_nine):
    master = setup_master(staffed)
    put_teitori(master, "0722", "S", 4)
    set_takt(master, "0722", "S", "2", None)  # K2(面2)は目標タクトが無い
    sync_plans(staffed["app"])
    run_production(client, fake_clock, 150, 480)
    run_production(client, fake_clock, 600, 1, kitting_no=K2)  # 外す計画の長い時間は、分母に入らない
    e = eff(client)
    assert e["efficiency"] == pytest.approx(0.8)
    assert (e["included"], e["excluded"], e["reasons"]) == (1, 1, [{"reason": "no_takt", "count": 1}])


def test_plan_without_row_in_view_is_unknown(client, staffed, fake_clock, at_nine):
    kno = "0800-1-S-251014-03"
    insert_plan(staffed["db"], kitting_no=kno, file_no="0800", start="2026/10/21 09:00:00", end="2026/10/21 12:00:00")
    sync_plans(staffed["app"])
    run_production(client, fake_clock, 30, 10, kitting_no=kno)
    assert eff(client)["reasons"] == [{"reason": "no_row", "count": 1}]  # 行が無い組は「不明」


def test_line_event_overlap_is_not_counted(client, staffed, fake_clock, at_nine):
    setup_master(staffed)
    ok(start(client, "production"))
    fake_clock.advance(minutes=30)
    e1 = ok(ev_start(client, reason_id=reason_id("部品探し")))
    fake_clock.advance(minutes=30)
    ok(ev_end(client, e1["id"]))  # 9:30〜10:00 は工程と重なる
    fake_clock.advance(minutes=60)
    ok(end(client, "production", produced_qty=240))  # 9:00〜11:00 の工程
    fake_clock.advance(minutes=10)
    e2 = ok(ev_start(client, reason_id=reason_id("部品探し")))  # 11:10〜 は工程と重ならない
    fake_clock.advance(minutes=10)
    ok(ev_end(client, e2["id"]))
    e = eff(client)
    assert e["actual_seconds"] == 90 * 60  # 2時間 − 重なった30分
    assert e["efficiency"] == pytest.approx(3600 / 5400)  # 240台 ÷ 4 × 60秒


def test_voided_record_is_not_counted(client, staffed, fake_clock, at_nine):
    setup_master(staffed)
    run_production(client, fake_clock, 60, 240)
    mistaken = ok(start(client, "setup", kitting_no=K2))["event"]
    fake_clock.advance(minutes=300)
    ok(void(client, mistaken["id"], kitting_no=K2))
    e = eff(client)
    assert (e["actual_seconds"], e["included"]) == (3600, 1)


def test_open_record_counts_until_now(client, staffed, fake_clock, at_nine):
    setup_master(staffed)
    ok(start(client, "setup"))
    fake_clock.advance(minutes=45)
    assert eff(client)["actual_seconds"] == 45 * 60


def test_record_across_8_15_is_split_and_quantity_counts_where_it_ends(client, staffed, fake_clock):
    setup_master(staffed)
    run_production(client, fake_clock, 60, 180)  # 8:00〜9:00。8:15 の境目をまたぐ
    before, after = eff(client, "2026-10-20"), eff(client)
    assert (before["actual_seconds"], before["standard_seconds"]) == (15 * 60, 0)  # 良品は終わった稼働日に数える
    assert (after["actual_seconds"], after["standard_seconds"]) == (45 * 60, 2700)
    assert after["efficiency"] == pytest.approx(1.0)


def test_completed_plan_keeps_the_teitori_of_completion(client, staffed, fake_clock, at_nine):
    master = setup_master(staffed, teitori=4)
    run_production(client, fake_clock, 120, 240)
    ok(start(client, "cleanup"))
    fake_clock.advance(minutes=30)
    ok(end(client, "cleanup"))
    value = eff(client)["efficiency"]
    assert value == pytest.approx(3600 / 9000)
    put_teitori(master, "0722", "S", 8)  # 完了のあとに既存アプリで変わっても
    sync_plans(staffed["app"])
    assert eff(client)["efficiency"] == pytest.approx(value)  # 完了した計画は完了の写しの値


def test_working_plan_follows_the_current_teitori(client, staffed, fake_clock, at_nine):
    master = setup_master(staffed, teitori=4)
    run_production(client, fake_clock, 150, 480)
    put_teitori(master, "0722", "S", 8)
    sync_plans(staffed["app"])
    assert eff(client)["efficiency"] == pytest.approx(0.4)  # 作業中の計画は今の値


def test_lots_with_different_line_warn_and_use_first_lot(client, staffed, fake_clock, at_nine):
    master = setup_master(staffed)
    put_teitori(master, "0722", "T", 2)
    insert_plan(staffed["db"], kitting_no=K1, lot_no="L002", file_no="0722", line="T")  # 同じキッティングNo.で、ロットのラインが違う
    sync_plans(staffed["app"])
    run_production(client, fake_clock, 150, 480)
    e = eff(client)
    assert any("丁取りが違います" in w for w in e["warnings"])
    assert e["efficiency"] == pytest.approx(0.8)  # 最初のロットの値で計算する


# --- 進捗率 ---

KNO = "0900-1-S-251014-05"


def _plan(world, kno=KNO, start="2026/10/21 09:00:00", end="2026/10/21 19:00:00"):
    insert_plan(world["db"], kitting_no=kno, file_no="0900", start=start, end=end)
    sync_plans(world["app"])
    return kno


def test_progress_is_process_time_over_plan_time(client, staffed, fake_clock, at_nine):
    kno = _plan(staffed)  # 計画10時間
    ok(start(client, "setup", kitting_no=kno))
    fake_clock.advance(minutes=30)
    ok(end(client, "setup", kitting_no=kno))
    ok(start(client, "production", kitting_no=kno))
    fake_clock.advance(minutes=90)  # 段取り30分 + 生産1時間30分(作業中も今まで数える)
    p = board_plan(client, kno)
    assert p["in_progress"] is True and p["progress"] == pytest.approx(0.2)


def test_progress_over_100_percent_is_kept(client, staffed, fake_clock, at_nine):
    kno = _plan(staffed, end="2026/10/21 10:00:00")  # 計画1時間
    ok(start(client, "production", kitting_no=kno))
    fake_clock.advance(minutes=120)
    assert board_plan(client, kno)["progress"] == pytest.approx(2.0)


def test_progress_subtracts_line_event_overlap(client, staffed, fake_clock, at_nine):
    kno = _plan(staffed)
    ok(start(client, "production", kitting_no=kno))
    fake_clock.advance(minutes=60)
    e = ok(ev_start(client, reason_id=reason_id("部品探し")))
    fake_clock.advance(minutes=60)
    ok(ev_end(client, e["id"]))
    assert board_plan(client, kno)["progress"] == pytest.approx(0.1)  # 2時間 − 付帯作業1時間 = 1時間 ÷ 10時間


def test_progress_is_hidden_before_start_and_after_cleanup(client, staffed, fake_clock, at_nine):
    kno = _plan(staffed)
    p = board_plan(client, kno)
    assert (p["in_progress"], p["progress"]) == (False, None)  # 始めていない
    run_production(client, fake_clock, 30, 10, kitting_no=kno)
    assert board_plan(client, kno)["in_progress"] is True
    ok(start(client, "cleanup", kitting_no=kno))
    fake_clock.advance(minutes=10)
    ok(end(client, "cleanup", kitting_no=kno))
    p = board_plan(client, kno)
    assert (p["in_progress"], p["progress"], p["completed"]) == (False, None, True)  # 片付けが終われば出さない


def test_progress_without_plan_time_is_none(client, staffed, fake_clock, at_nine):
    kno = _plan(staffed, start="", end="")
    ok(start(client, "production", kitting_no=kno))
    fake_clock.advance(minutes=30)
    run = ok(client.get(f"/api/runs/{kno}"))
    assert (run["in_progress"], run["progress"]) == (True, None)


# --- 画面・日報・区間の CSV がそろう ---

@pytest.fixture
def admin(client, staffed):
    with new_session() as s:
        masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        admin_auth.set_password(s, "K0042", "right-pass-1")
    assert client.post("/api/admin/login", json=LOGIN, headers=H).status_code == 200
    return staffed


def test_board_daily_report_and_csv_agree(client, admin, fake_clock, at_nine):
    setup_master(admin)
    run_production(client, fake_clock, 60, 120)
    ok(start(client, "setup", kitting_no=K2))
    fake_clock.advance(minutes=30)
    ok(end(client, "setup", kitting_no=K2))
    run_production(client, fake_clock, 90, 100, kitting_no=K2)
    assert client.post("/api/admin/login", json=LOGIN, headers=H).status_code == 200  # 時計を進めたのでログインし直す

    screen = eff(client)["efficiency"]
    report = ok(client.get("/api/admin/reports/daily", params={"date": DAY, "line_code": "S"}))["efficiency"]["efficiency"]
    r = client.get("/api/admin/reports/intervals.csv", params={"from": DAY, "to": DAY, "line_code": "S"})
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"), newline="")))
    steps = [x for x in rows if x["区分"] == "工程"]
    standard = sum(float(x["目標タクト(秒)"]) * int(x["生産数"] or 0) / int(x["丁取り数"]) for x in steps)
    actual = sum(float(x["時間(分)"]) * 60 for x in steps)
    assert list(rows[0])[-2:] == ["目標タクト(秒)", "丁取り数"]
    assert screen == pytest.approx(report) == pytest.approx(standard / actual)


def test_unresolved_plans_are_listed_for_admin(client, admin):
    master = admin["app"] / "db" / "master.db"
    put_teitori(master, "0722", "S", None, "no_k_row")
    sync_plans(admin["app"])
    d = ok(client.get("/api/admin/teitori/unresolved"))
    assert d["unresolved"] == 2 and d["by_status"] == {"no_k_row": 2} and not d["truncated"]
    assert {(p["kitting_no"], p["file_no"], p["line_code"], p["status"]) for p in d["plans"]} == {
        (K1, "0722", "S", "no_k_row"), (K2, "0722", "S", "no_k_row")}
