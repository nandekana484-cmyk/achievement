"""ボタン操作の冪等性(開発指針 0-5)。"""

from app.db.models import ApiRequest, LineOperator, RunEvent
from records_helpers import K2, rid, count_rows, set_operator, start, end, ok, conflict


def test_resend_returns_first_result(client, staffed, fake_clock):
    request_id = rid()
    first = ok(start(client, "setup", request_id=request_id))
    fake_clock.advance(minutes=5)
    again = ok(start(client, "setup", request_id=request_id))

    assert again == first  # 最初の結果をそのまま返す
    assert count_rows(RunEvent) == 1

    end_id = rid()
    ended = ok(end(client, "setup", request_id=end_id))
    assert ok(end(client, "setup", request_id=end_id)) == ended  # 終了の再送も同じ
    assert ok(start(client, "setup", request_id=request_id)) == first  # 状態が変わっても、最初の結果
    assert count_rows(RunEvent) == 1


def test_same_request_id_with_different_content_is_rejected(client, staffed):
    request_id = rid()
    ok(start(client, "setup", request_id=request_id))
    conflict(start(client, "n1_check", request_id=request_id), "同じリクエストIDで、内容の異なる操作")
    conflict(start(client, "setup", kitting_no=K2, request_id=request_id), "同じリクエストIDで")
    conflict(end(client, "setup", request_id=request_id), "同じリクエストIDで")  # 別の操作に使い回した
    assert count_rows(RunEvent) == 1


def test_failed_request_can_be_retried_with_same_id(client, world):
    request_id = rid()
    conflict(start(client, "setup", request_id=request_id), "担当者が設定されていません")
    set_operator(client, world["yamada"])
    ok(start(client, "setup", request_id=request_id))  # 失敗した操作は記録しないので、同じIDで送り直せる
    assert count_rows(ApiRequest, request_id=request_id) == 1


def test_operator_change_is_idempotent(client, world):
    request_id = rid()
    body = {"request_id": request_id, "operator_id": world["yamada"]}
    first = ok(client.put("/api/lines/S/operator", json=body))
    assert ok(client.put("/api/lines/S/operator", json=body)) == first
    conflict(client.put("/api/lines/S/operator", json={**body, "operator_id": world["sato"]}), "同じリクエストIDで")
    assert count_rows(LineOperator) == 1
