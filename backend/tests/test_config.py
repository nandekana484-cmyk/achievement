from pathlib import Path

from app.core.config import load_config


def test_cancel_guard_defaults(tmp_path):
    cfg = load_config(tmp_path / "none.toml")
    assert (cfg.sync.cancel_guard_min, cfg.sync.cancel_guard_ratio) == (10, 0.3)


def test_cancel_guard_from_toml(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[sync]\ncancel_guard_min = 5\ncancel_guard_ratio = 0.5\n", encoding="utf-8")
    cfg = load_config(p)
    assert (cfg.sync.cancel_guard_min, cfg.sync.cancel_guard_ratio) == (5, 0.5)


def test_example_config_has_cancel_guard():
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "config.example.toml"
    cfg = load_config(example)
    assert (cfg.sync.cancel_guard_min, cfg.sync.cancel_guard_ratio) == (10, 0.3)
    assert cfg.sync.legacy_db_max_age_days == 120
    assert cfg.paths.legacy_app_dir is None  # 例ではコメントにしてある


def test_legacy_app_dir_and_max_age(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        '[paths]\nlegacy_app_dir = "C:/work/inventory/dist"\n[sync]\nlegacy_db_max_age_days = 30\n',
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.paths.legacy_app_dir == Path("C:/work/inventory/dist")
    assert cfg.sync.legacy_db_max_age_days == 30


def test_legacy_db_max_age_default(tmp_path):
    assert load_config(tmp_path / "none.toml").sync.legacy_db_max_age_days == 120


def test_removed_legacy_database_key_is_reported(tmp_path, caplog):
    p = tmp_path / "config.toml"
    p.write_text('[paths]\nlegacy_database = "../legacy-db/monthly.db"\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.paths.legacy_app_dir is None
    assert "legacy_database は使われなくなりました" in caplog.text
