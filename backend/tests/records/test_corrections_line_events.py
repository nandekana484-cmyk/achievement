"""付帯作業の訂正(時刻・理由・設備・記入の変更、取り消し)と、ラインと日付での訂正の履歴(開発指針 5.5)。"""

from app.db.models import LineEvent, RunCorrection
from records_helpers import at, conflict, count_rows, ev_end, ev_start, ok, reason_id, rid


def ev_fix(client, event_id, line="S", **body):
    body.setdefault("request_id", rid())
    body.setdefault("reason", "mistake")
    return client.patch(f"/api/lines/{line}/events/{event_id}", json=body)


def ev_void(client, event_id, line="S", **body):
    body.setdefault("request_id", rid())
    body.setdefault("reason", "mistake")
    return client.post(f"/api/lines/{line}/events/{event_id}/void", json=body)


def _event(client, fake_clock, reason="部品探し", minutes=20, **body):
    e = ok(ev_start(client, reason_id=reason_id(reason), **body))
    fake_clock.advance(minutes=minutes)
    return ok(ev_end(client, e["id"]))


def test_change_times_and_reason(client, staffed, equipment, fake_clock):
    e = _event(client, fake_clock)  # 8:00〜8:20 部品探し
    fake_clock.advance(minutes=10)

    r = ok(ev_fix(client, e["id"], start_at=at("08:05"), reason_id=reason_id("マシントラブル"),
                  equipment_id=equipment["own"], reason="mistake"))

    ev = r["event"]
    assert (ev["start_at"], ev["reason_name"], ev["equipment_name"]) == (at("08:05"), "マシントラブル", "マウンター1")
    changes = {c["field"]: c for c in r["correction"]["changes"]}
    assert changes["reason_id"]["before_name"] == "部品探し" and changes["reason_id"]["after_name"] == "マシントラブル"
    assert changes["equipment_id"]["before"] is None and changes["equipment_id"]["after_name"] == "マウンター1"
    assert r["correction"]["target_table"] == "line_events" and r["correction"]["line_event_reason_name"] == "マシントラブル"


def test_reason_field_rules(client, staffed, equipment, fake_clock):
    e = _event(client, fake_clock)
    conflict(ev_fix(client, e["id"], reason_id=reason_id("人員交代")), "付帯作業として使えません")
    conflict(ev_fix(client, e["id"], reason_id=reason_id("マシントラブル")), "設備を選んでください")
    conflict(ev_fix(client, e["id"], reason_id=reason_id("マシントラブル"), equipment_id=equipment["other"]),
             "このラインの設備ではありません")
    conflict(ev_fix(client, e["id"], reason_id=reason_id("その他トラブル"), reason_text=" "), "理由を記入してください")
    ok(ev_fix(client, e["id"], reason_id=reason_id("その他トラブル"), reason_text="エア漏れ"))
    conflict(ev_fix(client, e["id"], reason_text=""), "理由を記入してください")  # 記入が必要な理由のまま記入を消す
    conflict(ev_fix(client, e["id"], reason_id=None), "付帯作業の理由を選んでください")
    conflict(ev_fix(client, e["id"], start_at=at("08:10"), reason=""), "訂正の理由を選んでください")


def test_time_rules(client, staffed, fake_clock):
    closed = _event(client, fake_clock)  # 8:00〜8:20
    fake_clock.advance(minutes=10)
    opened = ok(ev_start(client, reason_id=reason_id("部品探し")))  # 8:30〜(終了していない)
    fake_clock.advance(minutes=10)

    conflict(ev_fix(client, closed["id"], end_at=at("07:59")), "終了の時刻より前")
    conflict(ev_fix(client, opened["id"], start_at=at("08:45")), "未来の時刻")
    conflict(ev_fix(client, opened["id"], end_at=at("08:35")), "終了のボタンで終了してください")
    conflict(ev_fix(client, opened["id"], start_at=at("08:10")), "同じ理由の付帯作業(10/21 8:00〜10/21 8:20)と時間が重なります")
    conflict(ev_fix(client, closed["id"], end_at=at("08:31")), "同じ理由の付帯作業(10/21 8:30〜(終了していない))")
    ok(ev_fix(client, opened["id"], start_at=at("08:20")))
    # 異なる理由どうしは重なってよい
    other = _event(client, fake_clock, reason="欠品")
    ok(ev_fix(client, other["id"], start_at=at("08:00")))


def test_void_line_event(client, staffed, fake_clock):
    opened = ok(ev_start(client, reason_id=reason_id("部品探し")))  # 押し間違い
    r = ok(ev_void(client, opened["id"]))
    assert r["event"]["voided_at"] is not None and r["correction"]["kind"] == "void"
    assert count_rows(LineEvent) == 1  # 消さない
    conflict(ev_end(client, opened["id"]), "取り消されています")
    conflict(ev_void(client, opened["id"]), "取り消した付帯作業は直せません")
    ok(ev_start(client, reason_id=reason_id("部品探し")))  # 取り消した記録は数えないので、また開始できる
    board = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    assert [e["voided_at"] is not None for e in board["line_events"]] == [True, False]  # 履歴のため返す


def test_outside_field_range(client, staffed, fake_clock):
    e = _event(client, fake_clock)
    fake_clock.advance(days=2)
    conflict(ev_fix(client, e["id"], start_at=at("08:05")), "管理画面から直してください")
    conflict(ev_void(client, e["id"]), "管理画面から直してください")


def test_idempotent_and_404(client, staffed, fake_clock):
    e = _event(client, fake_clock)
    request_id = rid()
    first = ok(ev_fix(client, e["id"], start_at=at("08:05"), request_id=request_id))
    assert ok(ev_fix(client, e["id"], start_at=at("08:05"), request_id=request_id)) == first
    assert count_rows(RunCorrection) == 1
    assert ev_fix(client, 999, start_at=at("08:05")).status_code == 404
    assert ev_fix(client, e["id"], line="T", start_at=at("08:05")).status_code == 404


def test_history_by_line_and_date(client, staffed, fake_clock):
    early = _event(client, fake_clock)  # 10/21 8:00 → 稼働日 10/20
    fake_clock.advance(minutes=30)  # 8:50 → 稼働日 10/21
    later = _event(client, fake_clock, reason="欠品")
    ok(ev_fix(client, early["id"], end_at=at("08:15")))
    fake_clock.advance(minutes=1)
    ok(ev_fix(client, later["id"], start_at=at("08:55")))
    fake_clock.advance(minutes=1)
    ok(ev_void(client, later["id"], reason="forgot"))

    day21 = ok(client.get("/api/lines/S/corrections", params={"date": "2026-10-21"}))
    assert [(c["kind"], c["target_id"]) for c in day21] == [("void", later["id"]), ("update", later["id"])]
    day20 = ok(client.get("/api/lines/S/corrections", params={"date": "2026-10-20"}))
    assert [c["target_id"] for c in day20] == [early["id"]]
    assert ok(client.get("/api/lines/S/corrections"))[0]["kind"] == "void"  # 省略すると今の稼働日(10/21)
    assert client.get("/api/lines/ZZ/corrections").status_code == 404
