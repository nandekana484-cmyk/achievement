"""生産記録票(AD-18)の印刷用データ。組み合わせは実績の書き出しと同じ読み方(AD-19)。

world の K1(1回目)と K2(2回目)は、発行順が違うので H ではつながらない(同じロットNo. L001・同じファイルNo. 0722)。
"""

from actuals_helpers import admin, finish, produce  # noqa: F401
from app.core.config import get_config
from app.db.models import AuditLog, RunEvent, SideLink
from legacy_fixture import deactivate
from records_helpers import K1, K2, at, conflict, count_rows, end, ev_end, ev_start, fix, ok, reason_id, start, sync_plans, void
from test_side_link_field import link, plans

URL = "/api/production-records"
P1 = "0722-1-S-251014-05"  # H で P2 とつながる
P2 = "0722-2-S-251014-05"
K5 = "0800-1-S-251014-03"  # 面2の無い面1


def sheet(client, kno):
    return ok(client.get(f"{URL}/{kno}"))


def rows(client, **params):
    return ok(client.get(URL, params=params))


def done(client, fake_clock, kno, qty=10):
    produce(client, fake_clock, kno, qty)
    finish(client, fake_clock, kno)


def trouble(client, fake_clock, minutes=5, text="吸着エラー"):
    r = ok(ev_start(client, reason_id=reason_id("その他トラブル"), reason_text=text))
    fake_clock.advance(minutes=minutes)
    ok(ev_end(client, r["id"]))


# --- 組み合わせ ---

def test_linked_pair_is_one_sheet_even_when_key_h_does_not_connect(client, admin, fake_clock):
    done(client, fake_clock, K1, 100)
    done(client, fake_clock, K2, 100)
    s = sheet(client, K2)
    assert (s["side2_unlinked"], s["side1"], s["side2_kitting_no"]) == (True, None, K2)  # 面1とつながっていない
    ok(link(client, K2, K1))
    for kno in (K1, K2):  # どちらの面から開いても同じ1枚
        s = sheet(client, kno)
        assert (s["side1"]["kitting_no"], s["side2"]["kitting_no"], s["side2_unlinked"]) == (K1, K2, False)
        assert [x["lot_no"] for x in s["lots"]] == ["L001"]
    assert [r["kitting_no"] for r in rows(client)] == [K2]  # 一覧も1組で1行


def test_key_h_pair_and_one_sided_product(client, admin, fake_clock):
    plans(admin, (P1, "L050", "1"), (P2, "L050", "2"), (K5, "L060", "1"))
    for k in (P1, P2, K5):
        done(client, fake_clock, k)
    assert (sheet(client, P1)["side2"]["kitting_no"], sheet(client, P2)["side1"]["kitting_no"]) == (P2, P1)
    one = sheet(client, K5)  # 面2の無い面1: 2回目は空欄
    assert (one["side2"], one["side2_unlinked"], one["side1"]["good_total"]) == (None, False, 10)


def test_quantities_a_b_c_come_from_the_plan(client, admin, fake_clock):
    done(client, fake_clock, K1, 100)
    ok(link(client, K2, K1))
    s = sheet(client, K1)
    assert s["lots"] == [{"lot_no": "L001", "produced": 300, "cumulative": 0, "ordered": 1000}]  # 既存アプリの数量・累計・発注数
    assert (s["file_no"], s["product_name"], s["qty_differs"]) == ("0722", "基板A", [])


def test_lots_are_the_union_of_both_faces(client, admin, fake_clock):
    plans(admin, (P1, "L050", "1"), (P1, "L051", "1"), (P2, "L050", "2"), (P2, "L052", "2"))
    done(client, fake_clock, P1)
    assert [x["lot_no"] for x in sheet(client, P1)["lots"]] == ["L050", "L051", "L052"]


# --- 印刷できる計画 ---

def test_only_completed_plans_are_printable(client, admin, fake_clock):
    produce(client, fake_clock, K1, 100)
    conflict(client.get(f"{URL}/{K1}"), "片付けが終わった")
    assert client.get(f"{URL}/9999-1-S-251014-01").status_code == 404
    finish(client, fake_clock, K1)
    s = sheet(client, K1)  # 片付けが終われば出る。相手が未着手でも1枚
    assert s["side1"]["completed"] and s["side2"] is None
    ok(link(client, K2, K1))
    s = sheet(client, K2)  # 片付けの終わった面があれば印刷でき、未完了の面は記録のある所まで
    assert (s["side1"]["completed"], s["side2"]["completed"]) == (True, False)


def test_cancelled_plan_is_not_listed(client, admin, fake_clock):
    done(client, fake_clock, K1, 100)
    deactivate(admin["db"], K1)
    sync_plans(admin["app"])
    assert rows(client) == []
    assert client.get(f"{URL}/{K1}").status_code == 404


# --- 欄 ---

def test_rows_per_record_and_corrections_are_reflected(client, admin, fake_clock):
    for step, minutes in (("setup", 10), ("n1_check", 5), ("first_article", 5)):
        ok(start(client, step)); fake_clock.advance(minutes=minutes); ok(end(client, step))
    produce(client, fake_clock, K1, 30, 40, 50)  # 区切り3つ
    ok(start(client, "xray")); fake_clock.advance(minutes=5); ok(end(client, "xray"))
    finish(client, fake_clock, K1)
    f = sheet(client, K1)["side1"]
    assert len(f["production"]) == 3 and f["good_total"] == 120
    assert f["setup"] == [{"date": "10/21", "worker": "鈴木", "start": "09:00", "end": "09:10"}]
    assert [len(f[k]) for k in ("n1_check", "first_article", "xray", "cleanup")] == [1, 1, 1, 1]
    # 取り消した区切りは出ない。時刻の訂正は今の値で出る
    prod = [e for e in ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]["events"] if e["step_type"] == "production"]
    ok(void(client, prod[0]["id"]))
    ok(fix(client, prod[1]["id"], start_at=at("09:35")))
    f = sheet(client, K1)["side1"]
    assert len(f["production"]) == 2 and f["production"][0]["start"] == "09:35" and f["good_total"] == 90


def test_troubles_are_limited_to_the_face_window_on_its_line(client, admin, fake_clock):
    trouble(client, fake_clock, text="前の付帯作業")  # 最初の工程より前
    fake_clock.advance(minutes=10)
    ok(start(client, "setup")); fake_clock.advance(minutes=5)
    trouble(client, fake_clock, 7, "窓の中")  # 最初の工程の開始から片付けの終了までの間
    fake_clock.advance(minutes=1)
    ok(end(client, "setup"))
    produce(client, fake_clock, K1, 10)
    finish(client, fake_clock, K1)
    fake_clock.advance(minutes=10)
    trouble(client, fake_clock, text="後の付帯作業")
    t = sheet(client, K1)["side1"]["troubles"]
    assert [(x["name"], x["start"], x["end"]) for x in t] == [("その他トラブル / 窓の中", "09:20", "09:27")]


def test_header_comes_from_config_and_defaults_to_the_form(client, admin, fake_clock, tmp_path):
    done(client, fake_clock, K1)
    h = sheet(client, K1)["header"]
    assert (h["approver"], h["checker"], h["author"], h["revision_date"], h["version"]) == ("木下", "北村", "シマダ", "2025/02/25", "02")
    cfg = tmp_path / "config.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + '[production_record]\napprover = "承認 太郎"\nversion = "1.2"\nchecker = ""\n', encoding="utf-8")
    get_config.cache_clear()
    h = sheet(client, K1)["header"]
    assert (h["approver"], h["version"], h["checker"], h["revision_date"]) == ("承認 太郎", "1.2", "", "2025/02/25")


# --- 一覧 ---

def test_list_filters_and_the_31_day_range(client, admin, fake_clock):
    plans(admin, (P1, "L050", "1"), (P2, "L050", "2"))
    done(client, fake_clock, K1)
    fake_clock.advance(minutes=30)
    done(client, fake_clock, P2)  # P1 は未完了、P2 は完了(H で P1 とつながる)
    all_rows = rows(client)
    assert [(r["kitting_no"], r["side2_unlinked"]) for r in all_rows] == [(P2, False), (K1, False)]  # 完了の新しい順
    p = all_rows[0]
    assert (p["side1_kitting_no"], p["side1_completed"], p["side2_completed"]) == (P1, False, True)  # どちらかの面が完了していれば出る
    assert [r["kitting_no"] for r in rows(client, kitting_no="251014-05")] == [P2]
    assert [r["kitting_no"] for r in rows(client, lot_no="l050")] == [P2]
    assert rows(client, line="T") == []
    assert [r["kitting_no"] for r in rows(client, line="S")] == [P2, K1]
    fake_clock.advance(days=30)  # 31日以内
    assert len(rows(client)) == 2
    fake_clock.advance(days=2)
    assert rows(client) == []


def test_unlinked_side2_is_listed_with_its_flag(client, admin, fake_clock):
    done(client, fake_clock, K2)
    assert [(x["kitting_no"], x["side2_unlinked"], x["side1_kitting_no"]) for x in rows(client)] == [(K2, True, None)]


# --- 読むだけ ---

def test_printing_does_not_change_records_or_links(client, admin, fake_clock):
    done(client, fake_clock, K1, 100)
    ok(link(client, K2, K1))
    before = (count_rows(RunEvent), count_rows(SideLink), count_rows(AuditLog))
    sheet(client, K1)
    rows(client)
    assert (count_rows(RunEvent), count_rows(SideLink), count_rows(AuditLog)) == before


def test_demo_seed_record_samples(client, world):
    import datetime as dt
    from app.db.models import Plan
    from app.services.demo_seed import seed_record_samples
    from records_helpers import new_session

    with new_session() as s:
        knos = seed_record_samples(s, dt.date(2026, 10, 21))
        assert knos == ["1300-1-R-261014-41", "1300-2-R-261014-41", "1301-1-R-261014-43", "1302-2-R-261014-45"]
        assert s.query(Plan).filter(Plan.kitting_no == knos[0]).count() == 10  # 10ロット
        assert {(p.planned_qty, p.cumulative_qty, p.order_qty) for p in s.query(Plan).filter(Plan.line_code == "R")} == {(100, 200, 300)}
