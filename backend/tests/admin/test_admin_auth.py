"""管理画面のログイン・セッション・パスワード。"""

import io

import pytest
from sqlalchemy import select

from app.db.models import AdminCredential, AuditLog, Operator
from app.db.session import get_sessionmaker
from app.domain.passwords import verify_password
from app.services import admin_auth
from app.services.errors import RuleViolation
from admin_helpers import H, PASSWORD, login


def _op(operator_id):
    return get_sessionmaker()().get(Operator, operator_id)


def _set(operator_id, **values):
    with get_sessionmaker()() as s:
        op = s.get(Operator, operator_id)
        for k, v in values.items():
            setattr(op, k, v)
        s.commit()


# --- パスワード ---

def test_password_is_stored_as_hash(people):
    with get_sessionmaker()() as s:
        first = s.get(AdminCredential, people["admin"]).password_hash
        assert first.startswith("scrypt$") and PASSWORD not in first
        assert verify_password(PASSWORD, first) and not verify_password("wrong-pass", first)
        admin_auth.set_password(s, "K0042", PASSWORD)  # 同じパスワードでもソルトが違うので、ハッシュは変わる
        s.expire_all()
        assert s.get(AdminCredential, people["admin"]).password_hash != first


def test_short_password_is_refused(people):
    with get_sessionmaker()() as s, pytest.raises(RuleViolation, match="8文字以上"):
        admin_auth.set_password(s, "K0042", "short7!")


def test_only_active_admins_can_have_a_password(people):
    with get_sessionmaker()() as s, pytest.raises(RuleViolation, match="管理者"):
        admin_auth.set_password(s, "Y001", "long-enough-1")


def test_change_password_needs_the_current_one(client, logged_in):
    body = {"current_password": "wrong-pass-1", "new_password": "new-pass-123"}
    r = client.put("/api/admin/password", json=body, headers=H)
    assert r.status_code == 409 and r.json()["detail"] == "今のパスワードが違います"
    r = client.put("/api/admin/password", json=body | {"current_password": PASSWORD, "new_password": "short"}, headers=H)
    assert r.status_code == 409 and "8文字以上" in r.json()["detail"]
    assert client.put("/api/admin/password", json=body | {"current_password": PASSWORD}, headers=H).status_code == 204
    assert login(client).status_code == 401
    assert login(client, password="new-pass-123").status_code == 200
    with get_sessionmaker()() as s:  # 変更は記録するが、パスワードそのものは残さない
        log = s.scalars(select(AuditLog).where(AuditLog.target_table == "admin_credentials")).all()
        assert log and all("new-pass" not in (row.after_json or "") for row in log)


# --- ログイン ---

def test_login_sets_an_httponly_strict_cookie(client, people):
    r = login(client, worker_id=" ｋ００４２ ")  # 作業者IDは正規化して照合する
    assert r.status_code == 200 and r.json()["worker_id"] == "K0042"
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api/admin" in cookie
    assert "Secure" not in cookie  # 社内LANの HTTP で使う
    assert client.get("/api/admin/me").json()["name"] == "管理 花子"


@pytest.mark.parametrize("worker_id,password", [("K0042", "wrong-pass-1"), ("NOBODY", PASSWORD), ("Y001", PASSWORD)])
def test_failure_does_not_tell_which_was_wrong(client, people, worker_id, password):
    r = login(client, worker_id, password)
    assert (r.status_code, r.json()["detail"]) == (401, "作業者IDかパスワードが違います")


def test_inactive_or_non_admin_cannot_log_in(client, people):
    _set(people["admin"], active=False)
    assert login(client).json()["detail"] == "作業者IDかパスワードが違います"
    _set(people["admin"], active=True, role="operator")
    assert login(client).status_code == 401
    _set(people["admin"], role="admin")
    assert login(client).status_code == 200


def test_five_failures_lock_for_five_minutes(client, people, fake_clock):
    for _ in range(5):
        assert login(client, password="wrong-pass-1").status_code == 401
    r = login(client)  # 正しいパスワードでも入れない
    assert r.status_code == 429 and "しばらくログインできません" in r.json()["detail"]
    fake_clock.advance(minutes=4)
    assert login(client).status_code == 429
    fake_clock.advance(minutes=1, seconds=1)
    assert login(client).status_code == 200


def test_success_resets_the_failure_count(client, people):
    for _ in range(4):
        login(client, password="wrong-pass-1")
    assert login(client).status_code == 200
    for _ in range(4):
        login(client, password="wrong-pass-1")
    assert login(client).status_code == 200  # 続けて5回ではないので止めない


# --- セッション ---

def test_losing_admin_role_locks_out_on_the_next_request(client, logged_in):
    assert client.get("/api/admin/me").status_code == 200
    _set(logged_in["admin"], role="operator")  # 既存アプリで admin でなくなった(計画の同期で反映)
    r = client.get("/api/admin/me")
    assert (r.status_code, r.json()["detail"]) == (401, "管理画面を使う権限がありません")
    _set(logged_in["admin"], role="admin")
    assert client.get("/api/admin/me").status_code == 401  # セッションは消えている


def test_idle_session_expires(client, logged_in, fake_clock):
    fake_clock.advance(minutes=20)
    assert client.get("/api/admin/me").status_code == 200  # 操作すると延びる
    fake_clock.advance(minutes=20)
    assert client.get("/api/admin/me").status_code == 200
    fake_clock.advance(minutes=31)
    r = client.get("/api/admin/me")
    assert (r.status_code, r.json()["detail"]) == (401, "ログインの有効期限が切れました。もう一度ログインしてください")


def test_session_ends_after_twelve_hours_even_if_active(client, logged_in, fake_clock):
    for _ in range(35):  # 20分ごとに操作して、11時間40分
        fake_clock.advance(minutes=20)
        assert client.get("/api/admin/me").status_code == 200
    fake_clock.advance(minutes=21)
    assert client.get("/api/admin/me").status_code == 401


def test_logout_ends_the_session(client, logged_in):
    assert client.post("/api/admin/logout", headers=H).status_code == 204
    assert client.get("/api/admin/me").status_code == 401


def test_admin_api_needs_a_session(client, people):
    for path in ("/api/admin/me", "/api/admin/equipment", "/api/admin/reasons", "/api/admin/lines", "/api/admin/operators"):
        assert client.get(path).status_code == 401, path
    assert client.post("/api/admin/equipment", json={"line_code": "S", "name": "x"}, headers=H).status_code == 401


def test_writes_without_the_header_are_refused(client, logged_in):
    r = client.post("/api/admin/equipment", json={"line_code": "S", "name": "新しい設備"})
    assert r.status_code == 403 and "X-Genba-Admin" in r.json()["detail"]
    assert client.post("/api/admin/login", json={"worker_id": "K0042", "password": PASSWORD}).status_code == 403
    assert client.get("/api/admin/equipment").status_code == 200  # 読むだけなら要らない


def test_field_api_needs_no_login(client, people):
    assert client.get("/api/masters").status_code == 200
    assert client.get("/api/lines/S/board", params={"date": "2026-10-21"}).status_code == 200


# --- 開発用コマンド ---

def test_cli_set_password(client, people, monkeypatch, capsys):
    from app import cli

    answers = iter(["cli-pass-123", "cli-pass-123"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    assert cli.main(["admin", "set-password", "--worker-id", "k0042"]) == 0
    assert "パスワードを設定しました" in capsys.readouterr().out
    assert login(client, password="cli-pass-123").status_code == 200

    answers = iter(["cli-pass-123", "different-1"])
    assert cli.main(["admin", "set-password", "--worker-id", "K0042"]) == 1
    assert "2回の入力が違います" in capsys.readouterr().err
    assert cli.main(["admin", "set-password", "--worker-id", "Y001"]) == 1  # 管理者ではない

    # PowerShell 5.1 から渡すと、先頭に BOM が付く
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO("\ufeffstdin-pass-12\r\n".encode("utf-8"))))
    assert cli.main(["admin", "set-password", "--worker-id", "K0042", "--stdin"]) == 0
    assert login(client, password="stdin-pass-12").status_code == 200


def test_unencodable_password_is_refused(people):
    with get_sessionmaker()() as s, pytest.raises(RuleViolation, match="使えない文字"):
        admin_auth.set_password(s, "K0042", "\udcefbroken-pass")


def test_me_returns_server_workday(client, logged_in, fake_clock):
    # テストの時計は 10/21 8:00(8:15 より前 = 前の稼働日)。8:15 になれば 10/21
    assert client.get("/api/admin/me").json()["workday"] == "2026-10-20"
    fake_clock.advance(minutes=15)
    assert client.get("/api/admin/me").json()["workday"] == "2026-10-21"


# --- 接続元IPごとの制限(S-07) ---

def test_failures_from_one_address_lock_that_address_even_for_other_ids(client, people, fake_clock):
    for i in range(20):  # 作業者IDを変えながら失敗する(IDごとの制限には当たらない)
        assert login(client, worker_id=f"NOBODY{i}", password="wrong-pass-1").status_code == 401
    r = login(client)  # 正しいIDとパスワードでも、この接続元は止まる
    assert r.status_code == 429 and "この端末" in r.json()["detail"]
    fake_clock.advance(minutes=4)
    assert login(client).status_code == 429
    fake_clock.advance(minutes=1, seconds=1)
    assert login(client).status_code == 200


def test_ip_failure_count_is_per_address_and_reset_by_success(client, people):
    from app.services.login_throttle import ip_throttle

    for i in range(19):
        login(client, worker_id=f"NOBODY{i}", password="wrong-pass-1")
    assert login(client).status_code == 200  # 成功で数え直す
    for i in range(19):
        login(client, worker_id=f"OTHER{i}", password="wrong-pass-1")
    assert login(client).status_code == 200
    ip_throttle.reset()
