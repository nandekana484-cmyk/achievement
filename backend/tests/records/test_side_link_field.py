"""現場の画面での面1と面2の紐づけ(AD-19)。明示の紐づけは書き出しでキー H より優先し、管理者の確定は待たない。

world の K1(0722-1-S-251014-01)と K2(0722-2-S-251014-02)は、発行順が違うので H ではつながらない(同じロットNo. L001・同じファイルNo. 0722)。
"""

import pytest

from actuals_helpers import DAY, H, URL, admin, by_key, export, finish, listing, login, produce  # noqa: F401
from app.db.models import AuditLog, ExportedRow, SideLink
from legacy_fixture import deactivate, insert_plan
from records_helpers import K1, K2, count_rows, new_session, ok, rid, sync_plans

P1 = "0722-1-S-251014-05"  # H で P2 とつながる
P2 = "0722-2-S-251014-05"
P3 = "0722-1-S-251013-09"  # 同じロットの面1(P2 とは H でつながらない)


def plans(admin, *specs, file_no="0722", line="S"):
    for kitting_no, lot_no, side in specs:
        insert_plan(admin["db"], kitting_no=kitting_no, lot_no=lot_no, side=side, qty=100, file_no=file_no, line=line)
    sync_plans(admin["app"])


def link_body(side1, **extra):
    return {"request_id": rid(), "worker_id": "Y100", "side1_kitting_no": side1, **extra}


def link(client, side2, side1, **extra):
    return client.post(f"/api/runs/{side2}/side-link", json=link_body(side1, **extra))


def unlink(client, side2):
    return client.post(f"/api/runs/{side2}/side-link/unlink", json={"request_id": rid(), "worker_id": "Y100"})


def check(client, side2, side1):
    return ok(client.post(f"/api/runs/{side2}/side-link/check", json={"side1_kitting_no": side1}))


def view(client, kno, date="2026-10-21"):
    boards = ok(client.get("/api/lines/S/board", params={"date": date}))["plans"]
    return next(p["side_link"] for p in boards if p["plan"]["kitting_no"] == kno)


def done(client, fake_clock, *knos):
    for k in knos:
        produce(client, fake_clock, k, 100)
        finish(client, fake_clock, k)


# --- 欄の候補 ---

def test_candidate_two_is_prefilled_when_exactly_one_side1_has_the_same_lot_and_file(client, admin):
    v = view(client, K2)
    assert (v["role"], v["partner"], v["suggested"], v["candidates"]) == ("side2", None, K1, [K1])  # H でつながらないが、候補2


def test_candidate_one_is_the_key_h_partner_and_several_candidates_are_listed(client, admin):
    plans(admin, (P1, "L050", "1"), (P2, "L050", "2"), (P3, "L050", "1"))
    v = view(client, P2)
    assert (v["suggested"], v["partner_source"], v["candidates"]) == (P1, "h", [P3, P1] if P3 < P1 else [P1, P3])  # 1. キー H
    plans(admin, ("0722-2-S-251014-77", "L050", "2"))  # H の相手が無く、面1が2つ(P1・P3)
    v = view(client, "0722-2-S-251014-77")
    assert v["suggested"] is None and set(v["candidates"]) == {P1, P3}  # 複数なら空欄にして、一覧から選ぶ


# --- 紐づける ---

def test_link_is_used_by_the_export_without_waiting_for_the_admin(client, admin, fake_clock):
    done(client, fake_clock, K1)
    ok(link(client, K2, K1))
    v = view(client, K2)
    assert (v["partner"], v["partner_source"], v["decided_by"]) == (K1, "field", "鈴木(Y100)")
    assert view(client, K1)["partner"] == K2  # 面1の画面は、紐づいた面2の表示だけ
    done(client, fake_clock, K2)
    rows = by_key(listing(client))
    assert (K1, "L001") not in rows  # 面1は面2の行にまとめる
    assert rows[(K2, "L001")]["side1_kitting_no"] == K1 and rows[(K2, "L001")]["exportable"] is True
    data = ok(client.get(URL, params=DAY))
    assert data["pending_links"] == 0 and data["link_checks"][0]["decided_source"] == "field"  # 管理画面には、現場の紐づけと分かる


def test_explicit_link_beats_key_h(client, admin, fake_clock):
    plans(admin, (P1, "L050", "1"), (P2, "L050", "2"), (P3, "L050", "1"))
    done(client, fake_clock, P1, P2, P3)
    assert view(client, P2)["suggested"] == P1
    ok(link(client, P2, P3))  # 明示の紐づけ(H の相手は P1)
    rows = by_key(listing(client))
    assert rows[(P2, "L050")]["side1_kitting_no"] == P3
    assert rows[(P1, "L050")]["exportable"] is False  # P2 は P3 に紐づいたので、P1 は H のつなぎ先を失う(未確定)


def test_redo_and_unlink_are_possible_any_time_and_keep_history(client, admin, fake_clock):
    plans(admin, (P1, "L050", "1"), (P2, "L050", "2"), (P3, "L050", "1"))
    ok(link(client, P2, P3))
    ok(link(client, P2, P1))  # 直す(最後に保存したものが有効)
    assert view(client, P2)["partner"] == P1
    ok(unlink(client, P2))  # 外す → キー H の自動のつなぎに戻る
    v = view(client, P2)
    assert (v["partner"], v["suggested"], v["partner_source"]) == (None, P1, "h")
    with new_session() as s:
        rows = s.query(SideLink).order_by(SideLink.id).all()
        assert [(r.action, r.side1_kitting_no, r.previous_partner, r.source) for r in rows] == [
            ("link", P3, P1, "field"), ("link", P1, P3, "field"), ("unlink", P1, P1, "field")]  # 履歴は消さない。前の相手も残る
    assert count_rows(AuditLog, target_table="side_links") == 3  # audit_log にも残る
    assert unlink(client, P2).status_code == 409  # 外すものが無い(キー H のつなぎは外せない)


def test_admin_confirm_can_overwrite_the_field_link_and_the_field_can_fix_it_back(client, admin, fake_clock):
    ok(link(client, K2, K1))
    login(client)
    assert client.post(f"{URL}/links", json={"lot_no": "L001", "side1_kitting_no": K1, "side2_kitting_no": None}, headers=H).status_code == 200
    assert view(client, K2)["partner"] is None  # 管理者が「つながない」にした
    ok(link(client, K2, K1))  # 管理者の確定のあとでも、作業者は直せる
    assert view(client, K2)["partner"] == K1


def test_input_is_normalized_before_searching(client, admin):
    assert check(client, K2, "　０７２２－１－Ｓ－２５１０１４－０１ ")["side1_kitting_no"] == K1  # 全角の数字・英字・ハイフン、前後の空白
    assert check(client, K2, K1.lower())["side1_kitting_no"] == K1  # 英字の大文字・小文字の違いは1つに決まれば当てる


# --- 確かめること(断る3つと警告1つ) ---

def test_refusals(client, admin):
    plans(admin, ("0800-1-S-251014-03", "L001", "1"), file_no="0800")
    assert "見つかりません" in check(client, K2, "0722-1-S-251014-99")["errors"][0]  # 面1の計画が無い
    assert "1回目(面1)の計画ではありません" in check(client, K2, K2)["errors"][0]
    assert "ファイルNo.が違います" in check(client, K2, "0800-1-S-251014-03")["errors"][0]  # ファイルNo.が違う
    assert link(client, K2, "0800-1-S-251014-03").status_code == 409
    assert check(client, K1, K1)["errors"] and check(client, K2, "")["errors"]  # 面1の計画には紐づけない、空


def test_side1_already_linked_to_another_side2_is_refused_with_the_partner(client, admin):
    plans(admin, (P1, "L001", "1"), (P2, "L001", "2"), (P3, "L001", "1"))
    err = check(client, K2, P1)["errors"][0]  # P1 はキー H で P2 とつながっている(相手を出して断る)
    assert "キッティングNo.で" in err and P2 in err
    ok(link(client, K2, P3))
    r = link(client, P2, P3)  # P3 は K2 と明示で紐づいている
    assert r.status_code == 409 and f"すでに {K2} と紐づいています。先に {K2} の紐づけを外してください" in r.json()["detail"]
    ok(unlink(client, K2))
    ok(link(client, P2, P3))  # 先に相手の紐づけを外せば、紐づけられる


def test_cancelled_plans_cannot_be_linked(client, admin):
    plans(admin, (P1, "L001", "1"))
    deactivate(admin["db"], P1)
    sync_plans(admin["app"])
    assert "取り消された計画" in check(client, K2, P1)["errors"][0]


def test_lot_mismatch_is_a_warning_that_can_be_confirmed(client, admin):
    plans(admin, ("0722-2-S-251014-60", "L001", "2"), ("0722-2-S-251014-60", "L002", "2"))  # 2回目はロットが2つ、1回目(K1)は L001 だけ
    chk = check(client, "0722-2-S-251014-60", K1)
    assert chk["errors"] == [] and chk["mismatched_lots"] == ["L002(2回目だけ)"]
    r = link(client, "0722-2-S-251014-60", K1)
    assert r.status_code == 409 and "ロットNo.の組が合いません" in r.json()["detail"]
    assert count_rows(SideLink) == 0
    assert link(client, "0722-2-S-251014-60", K1, confirm_lot_mismatch=True).status_code == 200  # 確認すれば紐づけられる


def test_operator_is_required_and_request_is_idempotent(client, admin):
    body = link_body(K1)
    assert client.post(f"/api/runs/{K2}/side-link", json={**body, "worker_id": "NOBODY"}).status_code in (404, 409)
    assert ok(client.post(f"/api/runs/{K2}/side-link", json=body))["partner"] == K1
    assert ok(client.post(f"/api/runs/{K2}/side-link", json=body))["partner"] == K1  # 再送は1件
    assert count_rows(SideLink) == 1
    assert client.post(f"/api/runs/{K2}/side-link", json={**body, "side1_kitting_no": P1}).status_code == 409  # 同じIDで内容が違う


def test_sides_on_different_lines_can_be_linked(client, admin, fake_clock):
    plans(admin, ("0722-1-A-251014-31", "L900", "1"), ("0722-2-C-251014-32", "L900", "2"))  # 1回目 Aライン、2回目 Cライン
    assert check(client, "0722-2-C-251014-32", "0722-1-A-251014-31")["errors"] == []
    ok(client.post("/api/runs/0722-2-C-251014-32/side-link", json=link_body("0722-1-A-251014-31")))
    produce(client, fake_clock, "0722-1-A-251014-31", 100)  # ラインが違っても、紐づけと書き出しはキッティングNo.の組


# --- 書き出し後の変更 ---

def test_exported_rows_are_recorded_and_changes_after_export_are_listed(client, admin, fake_clock):
    done(client, fake_clock, K1, K2)
    ok(link(client, K2, K1))
    assert export(client).status_code == 200
    assert count_rows(ExportedRow) >= 1
    chk = check(client, K2, P1 if False else K1)
    assert chk["exported"] is True and chk["current_partner"] == K1  # 保存の前に、画面が「書き出し済みです」と確認できる
    plans(admin, (P1, "L001", "1"))
    r = ok(link(client, K2, P1))  # 断らない(確認のあとなら保存できる)
    assert r["partner"] == P1
    login(client)
    changes = ok(client.get(f"{URL}/link-changes"))
    assert [(c["side2_kitting_no"], c["previous_partner"], c["new_partner"], c["changed_by"], c["source"]) for c in changes] == [
        (K2, K1, P1, "鈴木(Y100)", "field")]
    assert changes[0]["exported_at"] and changes[0]["changed_at"]
    checked = client.post(f"{URL}/link-changes/{changes[0]['id']}/check", headers=H)
    assert checked.status_code == 200 and ok(client.get(f"{URL}/link-changes")) == []  # 確認済みにすると、一覧から消える


def test_a_change_before_any_export_is_not_listed(client, admin, fake_clock):
    ok(link(client, K2, K1))
    login(client)
    assert ok(client.get(f"{URL}/link-changes")) == []


# --- 引き継ぎ(AD-16)で紐づけも移る ---

def test_handover_moves_the_link_to_the_new_kitting_no(client, admin, fake_clock):
    done(client, fake_clock, K1, K2)
    ok(link(client, K2, K1))
    new2 = "0722-2-S-251014-09"  # K2 を出し直したキッティングNo.
    insert_plan(admin["db"], kitting_no=new2, lot_no="L001", side="2", qty=300)
    deactivate(admin["db"], K2)
    sync_plans(admin["app"])
    login(client)
    r = client.post("/api/admin/handovers/confirm", json={"old_kitting_no": K2, "new_kitting_no": new2}, headers=H)
    assert r.status_code == 200, r.text
    assert view(client, new2)["partner"] == K1  # 紐づけも新しいキッティングNo.へ移る
    rows = by_key(listing(client))
    assert rows[(new2, "L001")]["side1_kitting_no"] == K1 and (K2, "L001") not in rows


def test_link_api_does_not_touch_the_records(client, admin, fake_clock):
    done(client, fake_clock, K1)
    before = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]["events"]
    ok(link(client, K2, K1))
    assert ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]["events"] == before  # 実績の記録は変えない
