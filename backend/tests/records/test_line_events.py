"""付帯作業(開発指針 5.5)。"""

from app.db.models import Line
from records_helpers import rid, new_session, reason_id, ok, conflict, ev_start, ev_end


def test_line_event_reason_rules(client, staffed, equipment):
    conflict(ev_start(client, reason_id=reason_id("人員交代")), "付帯作業として使えません")
    conflict(ev_start(client, reason_id=999), "付帯作業として使えません")
    conflict(ev_start(client, reason_id=reason_id("マシントラブル")), "マシントラブルでは、設備を選んでください")
    conflict(ev_start(client, reason_id=reason_id("マシントラブル"), equipment_id=equipment["other"]), "このラインの設備ではありません")
    conflict(ev_start(client, reason_id=reason_id("その他トラブル")), "その他トラブルでは、理由を記入してください")
    conflict(ev_start(client, reason_id=reason_id("その他トラブル"), reason_text="  "), "理由を記入してください")

    e = ok(ev_start(client, reason_id=reason_id("マシントラブル"), equipment_id=equipment["own"]))
    assert (e["reason_name"], e["equipment_name"], e["started_by_name"]) == ("マシントラブル", "マウンター1", "山田")
    t = ok(ev_start(client, reason_id=reason_id("その他トラブル"), reason_text="エア漏れ"))
    assert t["reason_text"] == "エア漏れ"


def test_line_event_overlap_rules(client, staffed):
    first = ok(ev_start(client, reason_id=reason_id("部品探し")))
    conflict(ev_start(client, reason_id=reason_id("部品探し")), "部品探しは開始されたまま終了していません")
    ok(ev_start(client, reason_id=reason_id("欠品")))  # 異なる理由どうしは重なってよい

    ended = ok(ev_end(client, first["id"], operator_id=staffed["sato"]))
    assert ended["end_at"] is not None and ended["ended_by_name"] == "佐藤"
    conflict(ev_end(client, first["id"]), "すでに終了しています")
    ok(ev_start(client, reason_id=reason_id("部品探し")))  # 終了したら、同じ理由をまた開始できる


def test_line_event_end_not_found(client, staffed):
    assert ev_end(client, 999).status_code == 404
    e = ok(ev_start(client, reason_id=reason_id("欠品")))
    with new_session() as s:
        s.add(Line(line_code="T", name="Tライン", active=True, sort_order=99))
        s.commit()
    assert ev_end(client, e["id"], line="T").status_code == 404  # 別のラインの付帯作業


def test_line_event_requires_operator(client, world):
    conflict(ev_start(client, reason_id=reason_id("欠品")), "担当者が設定されていません")


def test_line_event_idempotent(client, staffed):
    request_id = rid()
    first = ok(ev_start(client, reason_id=reason_id("欠品"), request_id=request_id))
    assert ok(ev_start(client, reason_id=reason_id("欠品"), request_id=request_id)) == first
    conflict(ev_start(client, reason_id=reason_id("部品探し"), request_id=request_id), "同じリクエストIDで")

    end_id = rid()
    ended = ok(ev_end(client, first["id"], request_id=end_id))
    assert ok(ev_end(client, first["id"], request_id=end_id)) == ended
