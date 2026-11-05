"""管理表の内容の Excel 取り込み(AD-28)のAPI: 確かめるだけでDBに書かない、登録と履歴、上書きの警告、戻せること、管理者だけ、上限の大きさ。"""

import json
import logging

from book_helpers import Cluster, SheetSpec, build_xls, build_xlsx, example_sheet
from sqlalchemy import func, select

from actuals_helpers import H, admin, login  # noqa: F401
from app.db.models import AuditLog, ControlSheetImport, ControlSheetVersion
from records_helpers import new_session, ok

BASE = "/api/admin/control-sheets"


def preview(client, data, filename="工程表.xlsx"):
    return client.post(f"{BASE}/import/preview", params={"filename": filename}, content=data, headers=H)


def apply(client, data, file_nos, filename="工程表.xlsx"):
    body = json.dumps({"file_nos": file_nos}).encode()
    return client.post(f"{BASE}/import/apply", params={"filename": filename}, content=f"{len(body):010d}".encode() + body + data, headers=H)


def book(*names):
    return build_xlsx(*[example_sheet(n, file_no_cell="") for n in names])


def counts():
    with new_session() as s:
        return (s.scalar(select(func.count()).select_from(ControlSheetVersion)), s.scalar(select(func.count()).select_from(ControlSheetImport)),
                s.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.target_table.like("control_sheet%"))))


def by_sheet(result):
    return {s["sheet_name"]: s for s in result["sheets"]}


def test_preview_classifies_and_writes_nothing(client, admin):
    login(client)
    ok(client.put(f"{BASE}/0800", json={"manager_no": "OLD", "rows": [{"name": "旧"}]}, headers=H))  # 登録済み(手で作った)
    before = counts()
    data = build_xlsx(example_sheet("722", file_no_cell=722), example_sheet("0800", file_no_cell=""), example_sheet("Sheet1"), example_sheet("0900", skip={"manager"}))
    result = ok(preview(client, data))
    assert counts() == before  # 確かめるだけ。DBには何も書かない
    s = by_sheet(result)
    assert (s["722"]["status"], s["722"]["file_no"], s["722"]["row_count"], s["722"]["manager_no"]) == ("new", "0722", 3, "MP-1")
    assert s["0800"]["status"] == "changed" and s["0800"]["overwrites_manual"] is True  # 管理画面で作った内容を上書きする
    fields = {(c["field"], c["row"]) for c in s["0800"]["changes"]}
    assert ("manager_no", None) in fields and ("row_count", None) in fields and ("name", 1) in fields
    assert (s["Sheet1"]["status"], s["Sheet1"]["file_no"]) == ("skipped", None) and "ファイルNo.の形" in s["Sheet1"]["reason"]
    assert s["0900"]["status"] == "error" and "管理No" in s["0900"]["reason"]
    assert result["counts"] == {"new": 1, "changed": 1, "skipped": 1, "error": 1}
    assert result["filename"] == "工程表.xlsx"


def test_apply_registers_with_history_and_audit(client, admin):
    login(client)
    data = book("0722", "0723", "0724")
    res = ok(apply(client, data, ["0722", "0724"]))  # 選んだものだけ
    assert (res["registered"], res["ignored"], res["filename"]) == (2, 0, "工程表.xlsx")
    cur = ok(client.get(f"{BASE}/0722", headers=H))
    assert (cur["action"], cur["import_id"], cur["import_filename"], cur["version"], cur["manager_no"], len(cur["rows"])) == ("import", res["import_id"], "工程表.xlsx", 1, "MP-1", 3)
    assert client.get(f"{BASE}/0723", headers=H).status_code == 404  # 選ばなかったシートは登録しない
    hist = ok(client.get(f"{BASE}/imports", headers=H))
    assert [(h["id"], h["filename"], h["imported_by_name"], h["sheet_count"], h["registered_count"]) for h in hist] == [(res["import_id"], "工程表.xlsx", "管理 花子", 3, 2)]
    with new_session() as s:
        batch = s.scalars(select(AuditLog).where(AuditLog.action == "control_sheet_import_batch")).one()
        assert json.loads(batch.after_json)["file_nos"] == ["0722", "0724"]
        assert len(s.scalars(select(AuditLog).where(AuditLog.action == "control_sheet_import")).all()) == 2  # シートごとにも残す


def test_overwrite_keeps_old_version_and_it_can_be_restored(client, admin):
    login(client)
    manual = ok(client.put(f"{BASE}/0722", json={"manager_no": "手", "rows": [{"name": "手で直した", "name_vi": "vi", "link": "run1"}]}, headers=H))
    s = by_sheet(ok(preview(client, book("0722"))))["0722"]
    assert s["status"] == "changed" and s["overwrites_manual"] is True
    ok(apply(client, book("0722"), ["0722"]))
    hist = ok(client.get(f"{BASE}/0722/history", headers=H))
    assert [(h["version"], h["action"]) for h in hist] == [(2, "import"), (1, "save")]
    assert hist[1]["rows"][0]["name"] == "手で直した"  # 上書きの前の内容は履歴から見られる
    # 戻す: 前の版の内容を保存し直す(AD-27 の履歴の仕組み)
    ok(client.put(f"{BASE}/0722", json={"manager_no": hist[1]["manager_no"], "rows": hist[1]["rows"]}, headers=H))
    assert ok(client.get(f"{BASE}/0722", headers=H))["rows"][0]["name"] == "手で直した" and manual["version"] == 1
    # もう一度取り込む(版 4)。そのあと同じブックを取り込んでも変更なしで、版は増えない
    ok(apply(client, book("0722"), ["0722"]))
    res = ok(apply(client, book("0722"), ["0722"]))
    assert res["registered"] == 0
    assert [h["version"] for h in ok(client.get(f"{BASE}/0722/history", headers=H))] == [4, 3, 2, 1]
    assert by_sheet(ok(preview(client, book("0722"))))["0722"]["status"] == "unchanged"


def test_changed_over_an_import_is_not_a_manual_overwrite(client, admin):
    login(client)
    ok(apply(client, book("0722"), ["0722"]))
    changed = build_xlsx(example_sheet("0722", file_no_cell="", manager_no="MP-2"))
    s = by_sheet(ok(preview(client, changed)))["0722"]
    assert (s["status"], s["overwrites_manual"]) == ("changed", False)  # 前の版が取り込みなら、警告は出さない
    assert [(c["field"], c["before"], c["after"]) for c in s["changes"]] == [("manager_no", "MP-1", "MP-2")]


def test_ignored_and_bad_requests(client, admin):
    login(client)
    ok(apply(client, book("0722"), ["0722"]))
    res = ok(apply(client, book("0722"), ["0722", "9999"]))  # 変更なし・ブックに無いシートは登録しない
    assert (res["registered"], res["ignored"]) == (0, 2)
    r = apply(client, book("0722"), [])
    assert r.status_code == 409 and "選ばれていません" in r.json()["detail"]
    assert apply(client, book("0722"), ["0722"], filename="a.csv").status_code == 409
    assert client.post(f"{BASE}/import/apply", params={"filename": "a.xlsx"}, content=b"abc", headers=H).status_code == 409  # 本文の形が違う


def test_xls_book_is_imported_too(client, admin):
    login(client)
    data = build_xls(example_sheet("0722", file_no_cell=""))
    assert by_sheet(ok(preview(client, data, "旧.xls")))["0722"]["row_count"] == 3
    ok(apply(client, data, ["0722"], "旧.xls"))
    assert ok(client.get(f"{BASE}/0722", headers=H))["rows"][1]["use_line"] is False  # 斜線は .xls からも読める


def test_only_admins_can_import(client, admin):
    data = book("0722")
    assert preview(client, data).status_code == 401
    assert apply(client, data, ["0722"]).status_code == 401
    assert client.get(f"{BASE}/imports").status_code == 401
    login(client)
    assert client.post(f"{BASE}/import/preview", params={"filename": "a.xlsx"}, content=data).status_code == 403  # X-Genba-Admin が無い


def test_body_limit_is_wider_only_for_the_import(client, admin):
    login(client)
    big = b"x" * (6 * 1024 * 1024)  # 通常の上限(5MB)を超える
    assert client.put(f"{BASE}/0722", content=big, headers=H).status_code == 413
    r = preview(client, big)  # 取り込みは 50MB まで。ブックではないので 409(413 ではない)
    assert r.status_code == 409 and "ブックを読めませんでした" in r.json()["detail"]
    assert preview(client, b"x" * (51 * 1024 * 1024)).status_code == 413


def test_import_limit_config(tmp_path):
    from app.core.config import ServerConfig, load_config

    assert ServerConfig().control_sheet_import_max_mb == 50
    (tmp_path / "c.toml").write_text("[server]\ncontrol_sheet_import_max_mb = 80\n", encoding="utf-8")
    assert load_config(tmp_path / "c.toml").server.control_sheet_import_max_mb == 80


def test_contents_are_not_logged(client, admin, caplog):
    login(client)
    secret = SheetSpec(name="0722", manager_no="極秘ノ管理番号", clusters=[Cluster(1, ["極秘ノ工程名"], ["極秘ノ作業要領"])])
    with caplog.at_level(logging.DEBUG):
        ok(preview(client, build_xlsx(secret, example_sheet("Sheet1"))))
        ok(apply(client, build_xlsx(secret), ["0722"]))
    assert "極秘" not in caplog.text  # 読んだ中身はログに書かない(件数とエラーの理由だけ)


def test_a_thousand_sheets_are_checked_and_registered_in_time(client, admin):
    import time

    login(client)
    clusters = [Cluster(k + 1, [f"工程{k + 1}", "社内", "INTERNO"], [f"作業要領 {j}" for j in range(1 + k % 4)], diagonal="up" if k % 3 == 0 else None, rows=1 + k % 5) for k in range(12)]
    data = build_xlsx(*[SheetSpec(name=f"{i:04d}", manager_no=f"MP-{i}", file_no_cell=i, clusters=clusters) for i in range(1, 1001)])
    t = time.perf_counter()
    result = ok(preview(client, data))
    checked = time.perf_counter() - t
    assert result["counts"] == {"new": 1000}
    t = time.perf_counter()
    assert ok(apply(client, data, [s["file_no"] for s in result["sheets"]]))["registered"] == 1000
    print(f"SHEETS1000 check {checked:.1f}s register {time.perf_counter() - t:.1f}s")
    assert checked < 60
    assert ok(preview(client, data))["counts"] == {"unchanged": 1000}
