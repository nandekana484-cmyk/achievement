"""ロットへの割り振りの保存(AD-18d): 保存したものを優先、合わないときは今の規則、差を引くロット、履歴、引き継ぎ、書き出しと生産記録票で同じ値。"""

import json

from actuals_helpers import BODY, H, URL, admin, by_key, export, finish, listing, login, produce  # noqa: F401
from app.db.models import AuditLog, LotAllocationChange
from records_helpers import K1, new_session, ok, rid
from test_handover import NEW, admin as handover_admin, complete_k1, confirm, reissue  # noqa: F401
from test_production_record import sheet
from test_side_link_field import plans
from sqlalchemy import select

P = "0722-1-S-251014-05"  # 3ロット(計画数 100 ずつ)の面1。面2は無い


def three_lots(admin, client, fake_clock, qty=298):
    plans(admin, (P, "L050", "1"), (P, "L051", "1"), (P, "L052", "1"))
    produce(client, fake_clock, P, qty)
    finish(client, fake_clock, P)


def alloc(client, kno=P, **params):
    return ok(client.get(f"/api/runs/{kno}/allocation", params=params))


def save(client, quantities, kno=P, worker="Y100"):
    who = {"worker_id": worker} if worker else {}  # 省略すると、そのラインの今の担当者
    return client.put(f"/api/runs/{kno}/allocation", json={"request_id": rid(), "quantities": quantities, **who})


def reset(client, kno=P):
    return client.post(f"/api/runs/{kno}/allocation/reset", json={"request_id": rid(), "worker_id": "Y100"})


def qtys(a):
    return [x["qty"] for x in a["lots"]]


def test_rule_is_used_until_something_is_saved(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    a = alloc(client)
    assert (qtys(a), a["saved"], a["stale"], a["editable"], a["total"], a["planned_total"]) == ([100, 100, 98], False, False, True, 298, 300)


def test_balance_lot_proposal_and_rejection_below_zero(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    first = alloc(client, balance_lot_no="L050")
    assert (qtys(first), first["proposal_error"]) == ([98, 100, 100], None)  # ほかのロットは計画数どおり、選んだロットで調整
    assert qtys(alloc(client, balance_lot_no="L051")) == [100, 98, 100]
    assert alloc(client)["saved"] is False  # 提案は保存しない


def test_balance_below_zero_is_refused(client, admin, fake_clock):
    plans(admin, ("0722-1-S-251014-06", "L060", "1"), ("0722-1-S-251014-06", "L061", "1"))
    produce(client, fake_clock, "0722-1-S-251014-06", 50)  # 計画 200 に対して 50(ほかのロット 100 を引くと 0 未満)
    finish(client, fake_clock, "0722-1-S-251014-06")
    a = alloc(client, kno="0722-1-S-251014-06", balance_lot_no="L060")
    assert a["proposal_error"] and "0 未満" in a["proposal_error"]
    assert qtys(a) == [50, 0]  # 提案は出さず、今の割り振りのまま


def test_saved_allocation_is_used_for_the_sheet_and_the_export(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    a = ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    assert (qtys(a), a["saved"], a["stale"]) == ([98, 100, 100], True, False)
    lots = {x["lot_no"]: x["actual"] for x in sheet(client, P)["lots"]}
    assert lots == {"L050": 98, "L051": 100, "L052": 100}
    login(client)
    exported = {k[1]: r["produced_qty"] for k, r in by_key(listing(client)).items()}
    assert exported == lots  # 書き出しと生産記録票で同じ値
    assert sheet(client, P)["allocation"]["saved"] is True


def test_sum_must_match_and_values_must_not_be_negative(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    assert save(client, {"L050": 100, "L051": 100, "L052": 100}).status_code == 409  # 合計 300 ≠ 298
    assert save(client, {"L050": 300, "L051": 0, "L052": -2}).status_code == 409
    assert save(client, {"L050": 298}).status_code == 409  # ロットの組が違う
    assert alloc(client)["saved"] is False


def test_worker_id_is_required(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    r = client.put(f"/api/runs/{P}/allocation", json={"request_id": rid(), "worker_id": "NOBODY", "quantities": {"L050": 98, "L051": 100, "L052": 100}})
    assert r.status_code >= 400
    assert alloc(client)["saved"] is False


def test_stale_when_production_is_corrected_after_saving(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    board = ok(client.get("/api/lines/S/board", params={"date": "2026-10-21"}))
    prod = next(e for p in board["plans"] for e in p["events"] if e["step_type"] == "production")
    r = client.patch(f"/api/runs/{P}/events/{prod['id']}", json={"request_id": rid(), "reason": "mistake", "worker_id": "Y100", "produced_qty": 290})
    assert r.status_code == 200, r.text
    a = alloc(client)
    assert (a["stale"], a["saved"], qtys(a)) == (True, False, [100, 100, 90])  # 保存したものは使わず、今の規則
    login(client)
    rows = listing(client)
    assert all(r["allocation_stale"] for r in rows if r["kitting_no"] == P)
    assert sum(r["produced_qty"] for r in rows if r["kitting_no"] == P) == 290


def test_reset_returns_to_the_rule_and_history_is_kept(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    assert reset(client).status_code == 409  # 保存したものが無い
    ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    ok(save(client, {"L050": 100, "L051": 98, "L052": 100}))
    a = ok(reset(client))
    assert (qtys(a), a["saved"]) == ([100, 100, 98], False)
    with new_session() as s:
        rows = list(s.scalars(select(LotAllocationChange).where(LotAllocationChange.kitting_no == P).order_by(LotAllocationChange.id)))
        assert [r.action for r in rows] == ["save", "save", "reset"]
        assert json.loads(rows[0].before_json) == {"L050": 100, "L051": 100, "L052": 98}
        assert json.loads(rows[1].before_json) == {"L050": 98, "L051": 100, "L052": 100}  # 前と後の値
        assert json.loads(rows[1].after_json) == {"L050": 100, "L051": 98, "L052": 100}
        assert all(r.changed_by and r.source == "field" for r in rows)
        audit = list(s.scalars(select(AuditLog).where(AuditLog.target_table == "lot_allocations", AuditLog.target_key == P)))
        assert [a.action for a in audit] == ["save", "save", "reset"]


def test_saving_the_same_values_again_adds_no_history(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    with new_session() as s:
        assert len(list(s.scalars(select(LotAllocationChange)))) == 1


def test_changing_after_export_is_listed_for_the_admin(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    assert export(client).status_code == 200
    ok(save(client, {"L050": 98, "L051": 100, "L052": 100}))
    assert alloc(client)["exported"] is True
    login(client)
    changes = ok(client.get("/api/admin/actuals/link-changes", headers=H))
    assert [(c["kind"], c["kitting_no"]) for c in changes] == [("allocation", P)]
    assert "L050 100 → 98" in changes[0]["detail"]
    done = ok(client.post(f"/api/admin/actuals/link-changes/{changes[0]['id']}/check?kind=allocation", headers=H))
    assert done["kind"] == "allocation"
    assert ok(client.get("/api/admin/actuals/link-changes", headers=H)) == []


def test_allocation_edited_on_the_export_screen_is_saved(client, admin, fake_clock):
    three_lots(admin, client, fake_clock)
    quantities = [{"kitting_no": P, "lot_no": "L050", "produced_qty": 98}, {"kitting_no": P, "lot_no": "L052", "produced_qty": 100}]
    assert export(client, quantities=quantities).status_code == 200
    a = alloc(client)
    assert (qtys(a), a["saved"]) == ([98, 100, 100], True)
    assert {x["lot_no"]: x["actual"] for x in sheet(client, P)["lots"]} == {"L050": 98, "L051": 100, "L052": 100}
    login(client)
    assert ok(client.get("/api/admin/actuals/link-changes", headers=H)) == []  # 書き出す値の保存は「書き出し後の変更」にしない


def test_handover_moves_the_saved_allocation(client, handover_admin, fake_clock):
    complete_k1(client, fake_clock, 150)
    ok(save(client, {"L001": 150}, kno=K1, worker=None))
    reissue(handover_admin)
    assert confirm(client).status_code == 200
    a = alloc(client, kno=NEW)
    assert (a["saved"], qtys(a)) == (True, [150])
    assert alloc(client, kno=K1)["saved"] is False
    with new_session() as s:
        assert [r.action for r in s.scalars(select(LotAllocationChange).order_by(LotAllocationChange.id))] == ["save", "handover_in", "handover_out"]
