"""実績のAPIのテストのフィクスチャ。"""

import pytest
from fastapi.testclient import TestClient

from app.db.models import Line
from app.services import masters
from legacy_fixture import insert_plan
from records_helpers import K1, K2, new_session, set_operator, sync_plans


@pytest.fixture
def client(tmp_path, monkeypatch, fake_clock):
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[paths]\ndatabase = "{(tmp_path / "api.db").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_config.cache_clear()


@pytest.fixture
def world(client, legacy_app, legacy_db):
    """計画2件(ラインS。K1 は数量300・タクト30秒)、作業者2人(山田・佐藤)。今の担当者は未設定。"""
    insert_plan(legacy_db, kitting_no=K1, qty=300)
    insert_plan(legacy_db, kitting_no=K2, side="2", qty=300, start="2026/10/21 13:00:00", end="2026/10/21 15:00:00")
    sync_plans(legacy_app)
    with new_session() as s:
        yamada = masters.add_operator(s, "山田").id
        sato = masters.add_operator(s, "佐藤").id
    return {"yamada": yamada, "sato": sato, "app": legacy_app, "db": legacy_db}


@pytest.fixture
def staffed(client, world):
    set_operator(client, world["yamada"])
    return world


@pytest.fixture
def equipment(staffed):
    with new_session() as s:
        s.add(Line(line_code="T", name="Tライン", active=True, sort_order=99))
        s.commit()
        own = masters.add_equipment(s, "S", "マウンター1").id
        other = masters.add_equipment(s, "T", "マウンター9").id
    return {"own": own, "other": other}
