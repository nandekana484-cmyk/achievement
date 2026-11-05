"""K社製品ロット管理票の、ファイルNo.ごとの内容(AD-27): 登録・直し・コピー・履歴・管理者だけが編集・未登録のときの印刷のデータ・A と C の値。"""

from sqlalchemy import select

from actuals_helpers import H, admin, login  # noqa: F401
from app.db.models import AuditLog, ControlSheetVersion
from records_helpers import K1, K2, new_session, ok
from test_side_link_field import plans

URL = "/api/admin/control-sheets"
ROWS = [
    {"name": "SMT-1", "name_vi": None, "kind": "internal", "procedure": "Side B", "use_line": True, "link": "run1"},
    {"name": "X線検査", "name_vi": "Kiểm tra X-quang", "kind": "internal", "procedure": "検査数 5 枚\nロケーション", "use_line": False, "link": "xray"},
]


def put(client, file_no="0722", manager_no="MP-1", rows=None):
    return client.put(f"{URL}/{file_no}", json={"manager_no": manager_no, "rows": ROWS if rows is None else rows}, headers=H)


def slip(client, kno=K1):
    return ok(client.get(f"/api/id-slips/{kno}"))


def test_register_then_print_data_has_the_content(client, admin):
    cs = slip(client)["control_sheet"]  # 未登録 → 空の8行(ライン名の欄は斜線なし = use_line が True)
    assert (cs["registered"], cs["manager_no"], len(cs["rows"])) == (False, "", 8)
    assert all(r["name"] == "" and r["procedure"] == "" and r["use_line"] is True for r in cs["rows"])
    login(client)
    saved = ok(put(client))
    assert (saved["file_no"], saved["version"], saved["manager_no"], saved["saved_by_name"]) == ("0722", 1, "MP-1", "管理 花子")
    cs = slip(client)["control_sheet"]
    assert cs["registered"] is True and cs["manager_no"] == "MP-1"
    assert [(r["name"], r["kind"], r["use_line"], r["procedure"]) for r in cs["rows"][:2]] == [("SMT-1", "internal", True, "Side B"), ("X線検査", "internal", False, "検査数 5 枚\nロケーション")]
    assert len(cs["rows"]) == 8 and all(r["name"] == "" and r["use_line"] is False for r in cs["rows"][2:])  # 足した空の行(斜線)
    assert slip(client, K2)["control_sheet"]["manager_no"] == "MP-1"  # 同じファイルNo.の2回目の計画も同じ内容


def test_a_and_c_come_from_planned_and_order_qty(client, admin):
    lot = slip(client)["lots"][0]
    assert (lot["lot_no"], lot["planned_qty"], lot["order_qty"]) == ("L001", 300, 1000)  # A = plans.planned_qty、C = plans.order_qty


def test_edit_keeps_history_and_audit(client, admin):
    login(client)
    ok(put(client))
    ok(put(client))  # 同じ内容なら版は足さない
    v2 = ok(put(client, manager_no="MP-2", rows=ROWS[:1]))
    assert v2["version"] == 2
    hist = ok(client.get(f"{URL}/0722/history"))
    assert [(h["version"], h["manager_no"], len(h["rows"])) for h in hist] == [(2, "MP-2", 1), (1, "MP-1", 2)]  # 前の版を見られる
    with new_session() as s:
        assert len(s.scalars(select(ControlSheetVersion)).all()) == 2  # 物理削除も更新もしない
        logs = s.scalars(select(AuditLog).where(AuditLog.target_table == "control_sheet_versions").order_by(AuditLog.id)).all()
        assert [(a.action, a.target_key) for a in logs] == [("control_sheet_save", "0722")] * 2
        assert logs[0].before_json is None and '"MP-2"' in logs[1].after_json and '"MP-1"' in logs[1].before_json


def test_row_checks(client, admin):
    login(client)
    blank = ok(put(client, rows=[{"name": "  ", "use_line": False}, {"name": "", "kind": "internal"}]))  # 空の行(手で書く行)も登録できる
    assert [(r["name"], r["procedure"], r["use_line"], r["kind"]) for r in blank["rows"]] == [("", "", False, "none"), ("", "", True, "internal")]
    rows = slip(client)["control_sheet"]["rows"]  # 登録した行がそのまま出て、8行になるまで下に空の行を足す
    assert len(rows) == 8 and [r["use_line"] for r in rows] == [False, True] + [False] * 6 and rows[1]["kind"] == "internal"
    assert put(client, rows=[{"name": "A", "kind": "nope"}]).status_code == 422
    assert put(client, file_no=" ").status_code in (404, 409)
    assert put(client, rows=[{"name": f"R{i}"} for i in range(101)]).status_code == 409
    long_rows = [{"name": f"R{i}", "procedure": "x\n" * 3} for i in range(20)]
    assert len(ok(put(client, rows=long_rows))["rows"]) == 20  # 何行でも(上限 100)
    assert len(slip(client)["control_sheet"]["rows"]) == 20  # 8行より多いときは足さない


def test_copy_makes_a_new_one_without_manager_no(client, admin):
    login(client)
    ok(put(client))
    c = ok(client.post(f"{URL}/0800/copy", json={"source_file_no": "0722"}, headers=H))
    assert (c["version"], c["manager_no"], c["action"], c["copied_from"], len(c["rows"])) == (1, "", "copy", "0722", 2)
    assert client.post(f"{URL}/0800/copy", json={"source_file_no": "0722"}, headers=H).status_code == 409  # 登録済みには上書きしない
    assert client.post(f"{URL}/0900/copy", json={"source_file_no": "9999"}, headers=H).status_code == 404  # コピー元が未登録
    with new_session() as s:
        assert s.scalars(select(AuditLog).where(AuditLog.action == "control_sheet_copy")).one().target_key == "0800"


def test_list_shows_registered_and_unregistered_plan_file_nos(client, admin):
    plans(admin, ("0950-1-S-251014-09", "L090", "1"), file_no="0950")
    login(client)
    ok(put(client))
    rows = {r["file_no"]: r for r in ok(client.get(URL))}
    assert rows["0722"]["registered"] is True and rows["0722"]["saved_by_name"] == "管理 花子" and rows["0722"]["row_count"] == 2
    assert rows["0950"]["registered"] is False and rows["0950"]["in_plans"] is True and rows["0950"]["product_name"]  # 計画にあって未登録
    assert list(rows)[0] == "0950"  # 未登録を先に


def test_only_admins_can_edit(client, admin):
    assert put(client).status_code == 401  # ログインなし
    assert client.get(URL).status_code == 401
    assert client.get(f"{URL}/0722/history").status_code == 401
    assert client.post(f"{URL}/0800/copy", json={"source_file_no": "0722"}, headers=H).status_code == 401
    login(client)
    assert client.put(f"{URL}/0722", json={"manager_no": "", "rows": []}).status_code == 403  # X-Genba-Admin ヘッダーが無い
    assert client.get(f"{URL}/0722", headers=H).status_code == 404  # 未登録
