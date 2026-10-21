"""工程の記録の記録者とルール(開発指針 5.4、5.6)。"""

from sqlalchemy import select

from app.db.models import RunEvent
from legacy_fixture import deactivate
from records_helpers import K1, K2, rid, new_session, sync_plans, count_rows, reason_id, set_operator, start, end, ok, conflict


def test_start_without_operator_is_rejected(client, world):
    conflict(start(client, "setup"), "担当者が設定されていません")
    assert count_rows(RunEvent) == 0


def test_explicit_operator_is_used_without_current(client, world):
    e = ok(start(client, "setup", operator_id=world["sato"]))["event"]
    assert e["started_by"] == world["sato"] and e["started_by_name"] == "佐藤"


def test_operator_change_between_start_and_end(client, world, fake_clock):
    set_operator(client, world["yamada"])
    ok(start(client, "production"))
    fake_clock.advance(minutes=30)
    set_operator(client, world["sato"])  # 人員交代
    fake_clock.advance(minutes=30)
    e = ok(end(client, "production", produced_qty=120))["event"]

    assert (e["started_by_name"], e["ended_by_name"]) == ("山田", "佐藤")
    assert e["start_at"] == "2026-10-21T08:00:00+09:00" and e["end_at"] == "2026-10-21T09:00:00+09:00"


def test_one_time_operator_override(client, world):
    set_operator(client, world["yamada"])
    e = ok(start(client, "setup", operator_id=world["sato"]))["event"]  # 1回の操作だけ別の人
    assert e["started_by_name"] == "佐藤"
    assert client.get("/api/lines/S/operator").json()["operator_name"] == "山田"

def test_unknown_plan_is_404(client, staffed):
    r = start(client, "setup", kitting_no="9999-1-S-251014-99")
    assert r.status_code == 404 and "計画" in r.json()["detail"]


def test_unknown_step_type_is_422(client, staffed):
    assert start(client, "lunch").status_code == 422


def test_cancelled_plan_cannot_start_but_can_end(client, staffed):
    ok(start(client, "setup"))
    deactivate(staffed["db"], K1)  # 既存側で消えた → 取消
    sync_plans(staffed["app"])

    conflict(start(client, "n1_check"), "取消になった計画は開始できません")
    ok(end(client, "setup"))


def test_double_start_is_rejected(client, staffed):
    ok(start(client, "setup"))
    conflict(start(client, "setup"), "段取りは開始されたまま終了していません")
    assert count_rows(RunEvent) == 1


def test_end_without_start_is_rejected(client, staffed):
    conflict(end(client, "first_article"), "初品チェックは開始されていません")
    ok(start(client, "first_article"))
    ok(end(client, "first_article"))
    conflict(end(client, "first_article"), "初品チェックは開始されていません")  # 終了済み


def test_production_end_requires_qty(client, staffed):
    ok(start(client, "production"))
    conflict(end(client, "production"), "生産数を入力してください")
    conflict(end(client, "production", produced_qty=-1), "0以上の整数")
    assert end(client, "production", produced_qty=1.5).status_code == 422  # 整数でない
    e = ok(end(client, "production", produced_qty=0))["event"]  # 0 はよい
    assert e["produced_qty"] == 0


def test_other_steps_reject_qty(client, staffed):
    ok(start(client, "setup"))
    conflict(end(client, "setup", produced_qty=10), "段取りの終了では、生産数は受け付けません")


def test_restart_reason_rules(client, staffed):
    conflict(start(client, "production", restart_reason_id=reason_id("人員交代")), "1回目の生産の開始では、再開理由は受け付けません")
    conflict(start(client, "setup", restart_reason_id=reason_id("人員交代")), "段取りの開始では、再開理由は受け付けません")

    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=100))
    conflict(start(client, "production"), "再開理由を選んでください")
    conflict(start(client, "production", restart_reason_id=reason_id("立上立会")), "生産の再開理由として使えません")
    conflict(start(client, "production", restart_reason_id=999), "生産の再開理由として使えません")

    e = ok(start(client, "production", restart_reason_id=reason_id("人員交代")))["event"]
    assert (e["seq"], e["restart_reason_name"]) == (2, "人員交代")


def test_restart_equipment_rules(client, staffed, equipment):
    machine = reason_id("マシントラブル")
    conflict(start(client, "production", equipment_id=equipment["own"]), "設備は、設備が必要な再開理由")  # 1回目
    conflict(start(client, "setup", equipment_id=equipment["own"]), "設備は、設備が必要な再開理由")  # ほかの工程
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=10))

    conflict(start(client, "production", restart_reason_id=reason_id("人員交代"), equipment_id=equipment["own"]),
             "設備は、設備が必要な再開理由")
    conflict(start(client, "production", restart_reason_id=machine, equipment_id=equipment["other"]),
             "このラインの設備ではありません")
    conflict(start(client, "production", restart_reason_id=machine, equipment_id=999), "このラインの設備ではありません")

    e = ok(start(client, "production", restart_reason_id=machine, equipment_id=equipment["own"]))["event"]
    assert (e["equipment_id"], e["equipment_name"]) == (equipment["own"], "マウンター1")
    ok(end(client, "production", produced_qty=10))

    # 設備は任意(設備が必要な再開理由でも、選ばなくてよい)
    e = ok(start(client, "production", restart_reason_id=machine))["event"]
    assert e["equipment_id"] is None and e["equipment_name"] is None
    ok(end(client, "production", produced_qty=10))

    plan = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))["plans"][0]
    assert [x["equipment_name"] for x in plan["events"]] == [None, "マウンター1", None]


def test_restart_equipment_is_part_of_request_content(client, staffed, equipment):
    ok(start(client, "production"))
    ok(end(client, "production", produced_qty=10))
    request_id = rid()
    body = {"request_id": request_id, "restart_reason_id": reason_id("マシントラブル")}
    first = ok(start(client, "production", equipment_id=equipment["own"], **body))
    assert ok(start(client, "production", equipment_id=equipment["own"], **body)) == first
    conflict(start(client, "production", **body), "同じリクエストIDで")  # 設備の有無が違う


def test_different_steps_may_overlap(client, staffed):
    ok(start(client, "production"))
    ok(start(client, "first_article"))  # 生産中に初品チェック
    ok(start(client, "xray"))
    ok(end(client, "first_article"))
    ok(end(client, "production", produced_qty=50))
    assert count_rows(RunEvent) == 3


def test_more_than_three_production_segments(client, staffed):
    reason = reason_id("トラブル停止")
    for i in range(5):  # 記録用紙は3欄だが、データ上は上限なし
        ok(start(client, "production", restart_reason_id=reason if i else None))
        ok(end(client, "production", produced_qty=10))
    with new_session() as s:
        seqs = list(s.scalars(select(RunEvent.seq).where(RunEvent.step_type == "production").order_by(RunEvent.seq)))
    assert seqs == [1, 2, 3, 4, 5]


def test_setup_can_be_redone(client, staffed):
    ok(start(client, "setup"))
    ok(end(client, "setup"))
    e = ok(start(client, "setup"))["event"]  # トラブルで別の計画に切り替え、戻ってから段取りをやり直す
    assert e["seq"] == 2
    ok(end(client, "setup"))


def test_seq_is_per_plan_and_step(client, staffed):
    ok(start(client, "setup"))
    assert ok(start(client, "setup", kitting_no=K2))["event"]["seq"] == 1
    assert ok(start(client, "n1_check"))["event"]["seq"] == 1
