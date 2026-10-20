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
