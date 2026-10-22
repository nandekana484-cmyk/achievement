from datetime import time
from pathlib import Path

import pytest

from app.core.config import ConfigError, app_home, config_path, load_config


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


# --- 基準のフォルダ(GENBA_HOME)。exe と開発で切り替わる ---

EXE = r"C:\GenbaApp\app\v1.0.0\GenbaApp.exe"


def test_home_for_exe_is_two_levels_above_the_exe():
    assert app_home({}, frozen=True, executable=EXE) == Path(r"C:\GenbaApp")


def test_genba_home_overrides_for_exe_and_dev(tmp_path):
    env = {"GENBA_HOME": str(tmp_path)}
    assert app_home(env, frozen=True, executable=EXE) == tmp_path
    assert app_home(env, frozen=False) == tmp_path


def test_dev_without_genba_home_uses_the_started_folder():
    assert app_home({}, frozen=False) is None
    assert config_path({}, None) == Path("data/config.toml")  # 起動したフォルダから見た位置(今までどおり)


def test_config_is_read_from_home_and_relative_paths_follow_home(tmp_path):
    home = tmp_path / "GenbaApp"
    (home / "data").mkdir(parents=True)
    (home / "data" / "config.toml").write_text(
        '[paths]\nexchange_dir = "exchange"\nbackup_dir = "//server/share/backup"\nlegacy_app_dir = "C:/Inventory"\n',
        encoding="utf-8",
    )
    assert config_path({}, home) == home / "data" / "config.toml"
    cfg = load_config(config_path({}, home), home)
    assert cfg.home == home
    assert cfg.paths.database == home / "data" / "genba.db"  # 書いていない項目の既定値も基準から
    assert cfg.paths.exchange_dir == home / "exchange"
    assert cfg.paths.log_dir == home / "logs"
    assert cfg.paths.backup_dir == Path("//server/share/backup")  # 絶対パスはそのまま
    assert cfg.paths.legacy_app_dir == Path("C:/Inventory")


def test_missing_config_in_home_uses_defaults_under_home(tmp_path):
    cfg = load_config(config_path({}, tmp_path), tmp_path)
    assert cfg.paths.database == tmp_path / "data" / "genba.db"
    assert cfg.paths.backup_dir is None


def test_genba_config_overrides_the_config_location(tmp_path):
    assert config_path({"GENBA_CONFIG": str(tmp_path / "x.toml")}, tmp_path) == tmp_path / "x.toml"


def test_backup_settings(tmp_path):
    assert (load_config(tmp_path / "none.toml").backup.daily_at, load_config(tmp_path / "none.toml").backup.keep) == (time(12, 30), 30)
    p = tmp_path / "config.toml"
    p.write_text('[backup]\ndaily_at = "03:00"\nkeep = 7\n', encoding="utf-8")
    cfg = load_config(p)
    assert (cfg.backup.daily_at, cfg.backup.keep) == (time(3, 0), 7)


def test_config_with_bom_can_be_read(tmp_path):
    # メモ帳の「UTF-8(BOM 付き)」や PowerShell 5.1 の Out-File -Encoding utf8 で保存したもの
    p = tmp_path / "config.toml"
    p.write_bytes("﻿[server]\nport = 8771\n# 日本語のコメント\n".encode("utf-8"))
    assert load_config(p).server.port == 8771


def test_broken_config_tells_where(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[server\nport = 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="config.toml の書き方に誤りがあります"):
        load_config(p)


def test_admin_settings(tmp_path):
    cfg = load_config(tmp_path / "none.toml").admin
    assert (cfg.idle_minutes, cfg.max_hours, cfg.lockout_failures, cfg.lockout_minutes) == (30, 12, 5, 5)
    p = tmp_path / "config.toml"
    p.write_text("[admin]\nidle_minutes = 10\nlockout_failures = 3\n", encoding="utf-8")
    cfg = load_config(p).admin
    assert (cfg.idle_minutes, cfg.max_hours, cfg.lockout_failures, cfg.lockout_minutes) == (10, 12, 3, 5)
    example = load_config(Path(__file__).resolve().parents[2] / "config.example.toml").admin
    assert (example.idle_minutes, example.max_hours) == (30, 12)


def test_corrections_settings(tmp_path):
    assert load_config(tmp_path / "none.toml").corrections.field_margin_hours == 12  # 既定はタイムテーブルの表示範囲と同じ
    p = tmp_path / "c.toml"
    p.write_text("[corrections]\nfield_margin_hours = 24\n", encoding="utf-8")
    assert load_config(p).corrections.field_margin_hours == 24
    example = load_config(Path(__file__).resolve().parents[2] / "config.example.toml").corrections
    assert example.field_margin_hours == 12
