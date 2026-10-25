"""実績の書き出しの、面1と面2のひも付け(キー H = ロットNo. + キッティングNo.の回を除いた部分)と「ひも付けの確認」。

world の K1(0722-1-S-251014-01)と K2(0722-2-S-251014-02)は、発行順が違うので H ではつながらない。
"""

import pytest

from actuals_helpers import DAY, H, URL, admin, by_key, export, finish, listing, login, ng, produce  # noqa: F401
from app.db.models import SideLink
from legacy_fixture import insert_plan
from records_helpers import K1, K2, count_rows, sync_plans

P1 = "0722-1-S-251014-05"  # H で P2 とつながる(回だけが違う)
P2 = "0722-2-S-251014-05"
LINKS = f"{URL}/links"


def _plans(admin, *specs):
    for kitting_no, lot_no, side in specs:
        insert_plan(admin["db"], kitting_no=kitting_no, lot_no=lot_no, side=side, qty=100)
    sync_plans(admin["app"])


def _all(client):
    login(client)
    r = client.get(URL, params=DAY)
    assert r.status_code == 200, r.text
    return r.json()


def _confirm(client, side1, side2, lot="L001"):
    login(client)
    return client.post(LINKS, json={"lot_no": lot, "side1_kitting_no": side1, "side2_kitting_no": side2}, headers=H)


# --- キー H ---

def test_same_key_except_run_is_merged_into_the_side2_row(client, admin, fake_clock):
    _plans(admin, (P1, "L050", "1"), (P2, "L050", "2"))
    produce(client, fake_clock, P1, 100)
    ng(client, P1, "L050", 1, 5)
    finish(client, fake_clock, P1)
    produce(client, fake_clock, P2, 98)
    ng(client, P2, "L050", 2, 3)
    finish(client, fake_clock, P2)
    data = _all(client)
    [row] = [r for r in data["rows"] if r["lot_no"] == "L050"]
    assert (row["kitting_no"], row["side1_kitting_no"], row["ng_side1"], row["ng_side2"], row["exportable"]) == (P2, P1, 5, 3, True)
    assert not [c for c in data["link_checks"] if c["lot_no"] == "L050"]  # 確認は要らない


def test_side1_ng_entered_on_the_side2_screen_is_used(client, admin, fake_clock):
    _plans(admin, (P1, "L050", "1"), (P2, "L050", "2"))
    produce(client, fake_clock, P2, 100)
    ng(client, P2, "L050", 1, 7)  # 面2の画面から面1のNG
    finish(client, fake_clock, P2)
    r = by_key(listing(client))[(P2, "L050")]
    assert (r["ng_side1"], r["ng_side2"]) == (7, 0)
    assert any("面1の計画" in n and "完了していません" in n for n in r["notes"])


@pytest.mark.parametrize("side1", ["0722-1-S-251013-05", "0722-1-S-251014-06", "0722-1-T-251014-05"])
def test_different_date_seq_or_line_does_not_join(client, admin, fake_clock, side1):
    _plans(admin, (side1, "L050", "1"), (P2, "L050", "2"))
    produce(client, fake_clock, side1, 100)
    finish(client, fake_clock, side1)
    data = _all(client)
    r = by_key(data["rows"])[(side1, "L050")]
    assert r["exportable"] is False and "ひも付けの確認" in r["warnings"][0]
    assert data["pending_links"] == 1


# --- 単独の面1・面2 ---

def test_side2_without_any_side1_is_exported_alone_with_a_note(client, admin, fake_clock):
    _plans(admin, ("0950-2-S-251014-08", "L070", "2"))
    produce(client, fake_clock, "0950-2-S-251014-08", 80)
    ng(client, "0950-2-S-251014-08", "L070", 2, 1)
    finish(client, fake_clock, "0950-2-S-251014-08")
    r = by_key(listing(client))[("0950-2-S-251014-08", "L070")]
    assert (r["exportable"], r["side1_kitting_no"], r["ng_side1"], r["ng_side2"]) == (True, None, 0, 1)
    assert "つながる面1の計画が無いため、NG面1は0です" in r["notes"]


def test_side1_with_an_unjoined_side2_is_not_exported_and_is_listed_for_checking(client, admin, fake_clock):
    produce(client, fake_clock, K1, 300)
    finish(client, fake_clock, K1)
    data = _all(client)
    [row] = data["rows"]
    assert (row["kitting_no"], row["exportable"]) == (K1, False)
    [check] = data["link_checks"]
    assert (check["side1_kitting_no"], check["state"], check["suggested"], check["side1_completed"]) == (K1, "pending", K2, True)
    assert [c["kitting_no"] for c in check["candidates"]] == [K2]
    assert data["pending_links"] == 1
    r = export(client)
    assert r.status_code == 409 and "書き出せる行がありません" in r.json()["detail"]


def test_suggestion_is_the_nearest_issue_date(client, admin, fake_clock):
    _plans(admin, ("0722-2-S-251020-07", "L001", "2"), ("0722-2-S-251001-03", "L001", "2"))
    produce(client, fake_clock, K1, 300)
    finish(client, fake_clock, K1)
    [check] = _all(client)["link_checks"]
    assert [c["kitting_no"] for c in check["candidates"]] == ["0722-2-S-251001-03", K2, "0722-2-S-251020-07"]
    assert check["suggested"] == K2  # K1 と同じ 10/14


# --- 確定・やり直し・つながない ---

def test_confirm_merges_the_side1_lot_into_the_chosen_side2(client, admin, fake_clock):
    produce(client, fake_clock, K1, 300)
    ng(client, K1, "L001", 1, 4)
    finish(client, fake_clock, K1)
    r = _confirm(client, K1, K2)
    assert r.status_code == 200
    assert (r.json()["state"], r.json()["side2_kitting_no"], r.json()["decided_by"]) == ("confirmed", K2, "管理 花子(K0042)")
    data = _all(client)
    assert data["rows"] == [] and data["pending_links"] == 0  # 面1は面2の行にまとめる(面2はまだ完了していない)
    assert data["link_checks"][0]["state"] == "confirmed"  # やり直せるよう、確定したものも出す

    produce(client, fake_clock, K2, 290)
    finish(client, fake_clock, K2)
    row = by_key(_all(client)["rows"])[(K2, "L001")]
    assert (row["side1_kitting_no"], row["ng_side1"], row["exportable"]) == (K1, 4, True)
    assert not any("NG面1は0" in n for n in row["notes"])


def test_redo_and_unlink_keep_the_history(client, admin, fake_clock):
    produce(client, fake_clock, K1, 300)
    finish(client, fake_clock, K1)
    assert _confirm(client, K1, K2).status_code == 200
    r = _confirm(client, K1, None)  # つながない(面1は書き出さない)
    assert (r.status_code, r.json()["state"], r.json()["side2_kitting_no"]) == (200, "unlinked", None)
    row = by_key(_all(client)["rows"])[(K1, "L001")]
    assert row["exportable"] is False and "「つながない」にした" in row["warnings"][0]
    assert _confirm(client, K1, K2).json()["state"] == "confirmed"  # やり直し
    assert count_rows(SideLink) == 3  # 履歴は消さない(最新の行を使う)


def test_a_side2_already_joined_cannot_be_chosen(client, admin, fake_clock):
    late = "0722-1-S-251013-09"  # P2 と H でつながらない、同じロットの面1
    _plans(admin, (P1, "L050", "1"), (P2, "L050", "2"), (late, "L050", "1"))
    produce(client, fake_clock, late, 100)
    finish(client, fake_clock, late)
    [check] = [c for c in _all(client)["link_checks"] if c["side1_kitting_no"] == late]
    assert check["candidates"] == [{"kitting_no": P2, "issue_date": "2025-10-14", "paired_with": P1}]
    assert check["suggested"] is None
    r = _confirm(client, late, P2, lot="L050")
    assert r.status_code == 409 and f"すでに面1の計画 {P1} とつながっています" in r.json()["detail"]


def test_confirm_is_refused_when_not_needed_or_invalid(client, admin, fake_clock):
    _plans(admin, (P1, "L050", "1"), (P2, "L050", "2"))
    assert "確定は要りません" in _confirm(client, P1, P2, lot="L050").json()["detail"]  # H でつながっている
    assert _confirm(client, K1, "0722-2-S-251014-99").status_code == 409  # 面2の計画ではない
    assert _confirm(client, "0722-1-S-251014-99", K2).status_code == 404
    assert _confirm(client, K2, None).status_code == 404  # 面2の計画は面1として確定できない


def test_link_api_requires_admin_login_and_header(client, admin):
    body = {"lot_no": "L001", "side1_kitting_no": K1, "side2_kitting_no": K2}
    assert client.post(LINKS, json=body, headers=H).status_code == 401
    login(client)
    assert client.post(LINKS, json=body).status_code == 403  # 決まったヘッダーが無い
    assert count_rows(SideLink) == 0


# --- CSV の「面1のキッティングNo.」(書式版 2) ---

def _csv_by_kitting(client):
    """書き出した CSV を、(キッティングNo., ロットNo.) → 行の辞書にする。"""
    import csv
    import io

    from actuals_helpers import BODY

    login(client)
    res = client.post(f"{URL}/export", json=BODY, headers=H)
    assert res.status_code == 200, res.text
    data = client.get(f"{URL}/exports/{res.json()['id']}/file").content
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    assert rows and rows[0]["書式版"] == "2" and len(rows[0]) == 13
    return {(r["キッティングNo."], r["ロットNo."]): r for r in rows}


def test_csv_has_the_side1_kitting_no_for_every_way_of_joining(client, admin, fake_clock):
    # キー H でつながる組(NG面1 は 0)
    _plans(admin, (P1, "L050", "1"), (P2, "L050", "2"))
    produce(client, fake_clock, P1, 100)
    finish(client, fake_clock, P1)
    produce(client, fake_clock, P2, 100)
    finish(client, fake_clock, P2)
    # 管理者が確定した組(K1 と K2。発行順が違う)
    produce(client, fake_clock, K1, 300)
    finish(client, fake_clock, K1)
    assert _confirm(client, K1, K2).status_code == 200
    produce(client, fake_clock, K2, 300)
    finish(client, fake_clock, K2)
    # つながる面1が無い面2(単独)
    alone = "0950-2-S-251014-08"
    _plans(admin, (alone, "L070", "2"))
    produce(client, fake_clock, alone, 80)
    finish(client, fake_clock, alone)
    # 面2の計画が1件も無い面1(単独の面1の行)
    side1_only = "0800-1-S-251014-03"
    _plans(admin, (side1_only, "L010", "1"))
    produce(client, fake_clock, side1_only, 100)
    finish(client, fake_clock, side1_only)

    rows = _csv_by_kitting(client)
    assert rows[(P2, "L050")]["面1のキッティングNo."] == P1 and rows[(P2, "L050")]["NG面1"] == "0"  # NG面1 が 0 でも入る
    assert rows[(K2, "L001")]["面1のキッティングNo."] == K1  # 管理者が確定した組
    assert rows[(alone, "L070")]["面1のキッティングNo."] == ""  # つながる面1が無い
    assert rows[(side1_only, "L010")]["面1のキッティングNo."] == "" and rows[(side1_only, "L010")]["面"] == "1"  # 面1の行
    assert (P1, "L050") not in rows and (K1, "L001") not in rows  # 面1の行は面2にまとめる
