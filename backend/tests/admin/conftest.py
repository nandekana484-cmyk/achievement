"""管理画面のAPIのテストのフィクスチャ。管理者 K0042(パスワード right-pass-1)と、管理者でない作業者 Y001。"""

import pytest
from fastapi.testclient import TestClient

from app.db.models import Line
from app.db.session import get_sessionmaker
from admin_helpers import PASSWORD, login
from app.services import admin_auth, masters

@pytest.fixture
def client(tmp_path, monkeypatch, fake_clock):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "admin.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_config.cache_clear()


@pytest.fixture
def people(client):
    with get_sessionmaker()() as s:
        s.add(Line(line_code="S", name="Sライン", active=True, sort_order=10))
        s.commit()
        admin = masters.add_operator(s, "管理 花子", worker_id="K0042", role="admin")
        worker = masters.add_operator(s, "山田", worker_id="Y001")
        admin_auth.set_password(s, "K0042", PASSWORD)
    return {"admin": admin.id, "worker": worker.id}


@pytest.fixture
def logged_in(client, people):
    assert login(client).status_code == 200
    return people
