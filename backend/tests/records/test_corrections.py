"""工程の記録の訂正: 時刻・生産数の変更、取り消し、後からの追加とルール(開発指針 5.4 の「訂正」)。"""

from app.db.models import RunCorrection, RunEvent
from records_helpers import (
    K1, K2, add, at, board_plan, conflict, count_rows, end, fix, history, ok, reason_id, rid, start, void,
)


def _segment(client, fake_clock, minutes=60, qty=100, **start_body):
    """生産の区切りを1つ記録する(今から minutes 分)。"""
    e = ok(start(client, "production", **start_body))["event"]
    fake_clock.advance(minutes=minutes)
    ok(end(client, "production", produced_qty=qty))
    return e


def test_change_times_and_qty(client, staffed, fake_clock):
    e = _segment(client, fake_clock)  # 8:00〜9:00、100枚
    fake_clock.advance(minutes=30)

    r = ok(fix(client, e["id"], start_at=at("08:10"), end_at=at("09:05"), produced_qty=120, reason="wrong_qty",
               operator_id=staffed["sato"]))

    assert (r["event"]["start_at"], r["event"]["end_at"], r["event"]["produced_qty"]) == (at("08:10"), at("09:05"), 120)
    c = r["correction"]
    assert (c["kind"], c["reason"], c["reason_label"], c["source"]) == ("update", "wrong_qty", "数の入力の誤り", "field")
    assert (c["corrected_by_name"], c["corrected_at"], c["step_type"], c["seq"]) == ("佐藤", at("09:30"), "production", 1)
    assert [(x["field"], x["before"], x["after"]) for x in sorted(c["changes"], key=lambda x: x["field"])] == [
        ("end_at", at("09:00"), at("09:05")), ("produced_qty", 100, 120), ("start_at", at("08:00"), at("08:10")),
    ]
    assert board_plan(client)["produced_qty"] == 120
    assert r["completed"] is False and r["completion"] is None


def test_only_changed_fields_are_recorded(client, staffed, fake_clock):
    e = _segment(client, fake_clock)
    c = ok(fix(client, e["id"], start_at=at("08:00"), produced_qty=90))["correction"]
    assert [x["field"] for x in c["changes"]] == ["produced_qty"]  # 開始は同じ値なので変わっていない
    conflict(fix(client, e["id"], produced_qty=90), "変更がありません")
    conflict(fix(client, e["id"]), "直す項目を指定してください")


def test_corrector_is_current_operator_or_given(client, world, fake_clock):
    ok(start(client, "setup", operator_id=world["yamada"]))
    fake_clock.advance(minutes=10)
    ok(end(client, "setup", operator_id=world["yamada"]))
    ev = board_plan(client)["events"][0]
    conflict(fix(client, ev["id"], start_at=at("07:55")), "担当者が設定されていません")
    c = ok(fix(client, ev["id"], start_at=at("07:55"), operator_id=world["sato"]))["correction"]
    assert c["corrected_by_name"] == "佐藤"


def test_reason_is_required(client, staffed, fake_clock):
    e = _segment(client, fake_clock)
    conflict(fix(client, e["id"], produced_qty=1, reason=""), "訂正の理由を選んでください")
    conflict(fix(client, e["id"], produced_qty=1, reason="lunch"), "訂正の理由を選んでください")
    conflict(fix(client, e["id"], produced_qty=1, reason="other"), "内容を記入してください")
    conflict(fix(client, e["id"], produced_qty=1, reason="other", note="  "), "内容を記入してください")
    c = ok(fix(client, e["id"], produced_qty=1, reason="other", note="  数え直した "))["correction"]
    assert (c["reason_label"], c["note"]) == ("その他", "数え直した")
    assert count_rows(RunCorrection) == 1  # 失敗した訂正は残らない


def test_time_rules(client, staffed, fake_clock):
    first = _segment(client, fake_clock)  # 8:00〜9:00
    fake_clock.advance(minutes=30)
    second = _segment(client, fake_clock, restart_reason_id=reason_id("人員交代"))  # 9:30〜10:30
    fake_clock.advance(minutes=5)  # 今は 10:35

    conflict(fix(client, first["id"], end_at=at("07:59")), "開始の時刻は、終了の時刻より前にしてください")
    conflict(fix(client, first["id"], end_at=at("08:00")), "終了の時刻より前")  # 同じ時刻もだめ
    conflict(fix(client, second["id"], end_at=at("10:40")), "未来の時刻は入れられません")
    conflict(fix(client, first["id"], end_at=at("09:31")), "ほかの生産の区切り(10/21 9:30〜10/21 10:30)と時間が重なります")
    ok(fix(client, first["id"], end_at=at("09:30")))  # 接するだけならよい
    conflict(fix(client, first["id"], produced_qty=-1), "0以上の整数")
    assert fix(client, first["id"], start_at="2026-10-21T08:00:00").status_code == 422  # タイムゾーンの無い時刻


def test_open_record_rules(client, staffed, fake_clock):
    ok(start(client, "setup"))
    fake_clock.advance(minutes=20)
    ok(end(client, "setup"))  # 8:00〜8:20
    fake_clock.advance(minutes=10)
    opened = ok(start(client, "setup"))["event"]  # 8:30〜(段取りのやり直し。終了していない)
    fake_clock.advance(minutes=10)

    conflict(fix(client, opened["id"], end_at=at("08:35")), "終了していない記録の終了の時刻は直せません")
    # 終了していない記録の開始を、ほかの記録と矛盾する時刻にしない
    conflict(fix(client, opened["id"], start_at=at("08:10")), "ほかの段取りの記録(10/21 8:00〜10/21 8:20)と時間が重なります")
    conflict(fix(client, opened["id"], start_at=at("08:45")), "未来の時刻は入れられません")
    assert ok(fix(client, opened["id"], start_at=at("08:25")))["event"]["start_at"] == at("08:25")
    # 終了した記録も、終了していない記録とは重ねられない(生産以外の工程でも)
    first = board_plan(client)["events"][0]
    conflict(fix(client, first["id"], end_at=at("08:26")), "ほかの段取りの記録(10/21 8:25〜(終了していない))")

    ok(start(client, "production"))
    conflict(fix(client, board_plan(client)["events"][-1]["id"], produced_qty=5), "終了するときに入れてください")


def test_non_production_has_no_qty(client, staffed, fake_clock):
    ok(start(client, "setup"))
    fake_clock.advance(minutes=10)
    e = ok(end(client, "setup"))["event"]
    conflict(fix(client, e["id"], produced_qty=10), "段取りの記録には、生産数はありません")


def test_unknown_or_other_plans_event_is_404(client, staffed, fake_clock):
    e = _segment(client, fake_clock)
    assert fix(client, 9999, produced_qty=1).status_code == 404
    assert fix(client, e["id"], kitting_no=K2, produced_qty=1).status_code == 404


def test_outside_field_range_is_rejected(client, staffed, fake_clock):
    e = _segment(client, fake_clock)  # 10/21 8:00〜9:00
    fake_clock.advance(days=2)  # 10/23 9:00 → 現場で直せる範囲は 10/22 20:15〜10/24 20:15
    conflict(fix(client, e["id"], produced_qty=1), "管理画面から直してください")
    conflict(void(client, e["id"]), "管理画面から直してください")
    conflict(add(client, "setup", at("19:00", day=22), at("19:30", day=22)), "範囲の外の時刻は管理画面から直してください")
    ok(add(client, "setup", at("21:00", day=22), at("21:30", day=22)))


def test_new_times_must_be_in_field_range(client, staffed, fake_clock):
    e = _segment(client, fake_clock)  # 今は 10/21 9:00 → 範囲は 10/20 20:15〜10/22 20:15
    conflict(fix(client, e["id"], start_at=at("20:00", day=20)), "管理画面から直してください")
    ok(fix(client, e["id"], start_at=at("20:30", day=20)))


def test_void_marks_and_excludes(client, staffed, fake_clock):
    first = _segment(client, fake_clock, qty=100)
    fake_clock.advance(minutes=10)
    second = _segment(client, fake_clock, qty=50, restart_reason_id=reason_id("人員交代"))

    r = ok(void(client, second["id"], reason="mistake"))

    assert r["event"]["voided_at"] == at("10:10") and r["event"]["void_reason"] == "mistake"
    assert r["event"]["voided_by_name"] == "山田" and r["correction"]["kind"] == "void"
    plan = board_plan(client)
    assert plan["produced_qty"] == 100 and plan["progress"] == 100 / 300  # 生産数・進捗から外れる
    assert [e["id"] for e in plan["events"]] == [first["id"], second["id"]]  # 履歴のため、記録は返す
    assert count_rows(RunEvent) == 2  # 消さない
    conflict(void(client, second["id"]), "取り消した記録は直せません")
    conflict(fix(client, second["id"], produced_qty=1), "取り消した記録は直せません")


def test_void_open_record_allows_restart(client, staffed, fake_clock):
    opened = ok(start(client, "production"))["event"]  # 押し間違い
    ok(void(client, opened["id"]))
    # 取り消した記録は数えないので、次の生産の開始は1回目の扱い(再開理由は要らない)。番号は使い回さない
    again = ok(start(client, "production"))["event"]
    assert again["seq"] == 2 and again["restart_reason_id"] is None
    fake_clock.advance(minutes=5)
    ok(end(client, "production", produced_qty=10))


def test_add_forgotten_records(client, staffed, fake_clock):
    fake_clock.advance(hours=3)  # 11:00
    r = ok(add(client, "production", at("08:00"), at("09:00"), produced_qty=80))
    e = r["event"]
    assert (e["step_type"], e["seq"], e["added_later"], e["produced_qty"]) == ("production", 1, True, 80)
    assert (e["started_by_name"], e["ended_by_name"]) == ("山田", "山田")
    c = r["correction"]
    assert c["kind"] == "add" and c["reason"] == "forgot"
    assert {x["field"]: x["after"] for x in c["changes"]} == {
        "step_type": "production", "start_at": at("08:00"), "end_at": at("09:00"), "produced_qty": 80,
    }
    assert board_plan(client)["produced_qty"] == 80

    conflict(add(client, "production", at("08:30"), at("09:30"), produced_qty=1), "ほかの生産の区切り")
    conflict(add(client, "production", at("09:00"), at("09:30")), "0以上の整数")  # 生産数が必須
    conflict(add(client, "setup", at("07:00"), at("07:10"), produced_qty=1), "生産数はありません")
    conflict(add(client, "setup", at("10:00"), at("11:30")), "未来の時刻")
    conflict(add(client, "setup", at("10:00"), at("09:30")), "終了の時刻より前")
    assert add(client, "lunch", at("07:00"), at("07:10")).status_code == 422
    ok(add(client, "setup", at("07:30"), at("07:50")))


def test_idempotent_corrections(client, staffed, fake_clock):
    e = _segment(client, fake_clock)
    request_id = rid()
    first = ok(fix(client, e["id"], produced_qty=90, request_id=request_id))
    assert ok(fix(client, e["id"], produced_qty=90, request_id=request_id)) == first
    conflict(fix(client, e["id"], produced_qty=91, request_id=request_id), "同じリクエストID")

    add_id = rid()
    added = ok(add(client, "setup", at("07:00"), at("07:10"), request_id=add_id))
    assert ok(add(client, "setup", at("07:00"), at("07:10"), request_id=add_id)) == added
    assert count_rows(RunCorrection) == 2 and count_rows(RunEvent) == 2


def test_history_is_newest_first(client, staffed, fake_clock):
    e = _segment(client, fake_clock)
    ok(fix(client, e["id"], produced_qty=90))
    fake_clock.advance(minutes=1)
    ok(add(client, "setup", at("07:00"), at("07:10")))
    fake_clock.advance(minutes=1)
    ok(void(client, e["id"], reason="other", note="別の計画の生産だった"))

    h = history(client)
    assert [(c["kind"], c["step_type"]) for c in h] == [("void", "production"), ("add", "setup"), ("update", "production")]
    assert h[0]["note"] == "別の計画の生産だった" and h[0]["changes"][0]["field"] == "voided_at"
    assert history(client, K2) == []
    assert client.get("/api/runs/9999-1-S-251014-99/corrections").status_code == 404
