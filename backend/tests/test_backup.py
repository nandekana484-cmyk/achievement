"""本アプリのDBのバックアップ(開発指針 9)。"""

import sqlite3
from contextlib import closing
from datetime import datetime, time

from fastapi.testclient import TestClient

from app.core.clock import JST
from app.services.backup import backup_name, make_backup, prune_backups, seconds_until


def _db(path):
    with closing(sqlite3.connect(path)) as c, c:
        c.execute("CREATE TABLE t (x INTEGER)")
        c.execute("INSERT INTO t VALUES (1), (2)")
    return path


def _rows(path):
    with closing(sqlite3.connect(path)) as c:
        return c.execute("SELECT COUNT(*) FROM t").fetchone()[0]


def test_backup_is_saved_with_date_in_name(tmp_path, fake_clock):
    db = _db(tmp_path / "genba.db")
    saved = make_backup(db, tmp_path / "backup", keep=30, reason="daily")
    assert saved is not None and saved.name == "genba_20261021_080000_daily.db"
    assert _rows(saved) == 2  # SQLite のバックアップ機能で取った、開けるDB
    assert [p.name for p in (tmp_path / "backup").iterdir()] == [saved.name]  # 書きかけのファイルは残らない


def test_two_backups_in_the_same_second_get_different_names(tmp_path, fake_clock):
    db = _db(tmp_path / "genba.db")
    first = make_backup(db, tmp_path / "backup", keep=30, reason="startup")
    second = make_backup(db, tmp_path / "backup", keep=30, reason="startup")
    assert first != second and second.name == "genba_20261021_080000-2_startup.db"


def test_old_backups_beyond_keep_are_removed(tmp_path, fake_clock):
    db = _db(tmp_path / "genba.db")
    names = []
    for _ in range(5):
        fake_clock.advance(days=1)
        names.append(make_backup(db, tmp_path / "backup", keep=3, reason="daily").name)
    assert sorted(p.name for p in (tmp_path / "backup").iterdir()) == names[-3:]


def test_only_files_made_by_this_app_are_removed(tmp_path):
    folder = tmp_path / "backup"
    folder.mkdir()
    others = ["genba.db", "genba_20260101_000000_daily.db.bak", "other_20260101_000000_daily.db", "memo.txt"]
    for name in others:
        (folder / name).write_text("x")
    (folder / "sub").mkdir()
    ours = [backup_name(datetime(2026, 10, d, 12, 30, tzinfo=JST), "daily") for d in (1, 2, 3)]
    for name in ours:
        (folder / name).write_text("x")

    removed = prune_backups(folder, keep=1)

    assert sorted(p.name for p in removed) == ours[:2]
    assert sorted(p.name for p in folder.iterdir()) == sorted([*others, "sub", ours[2]])


def test_unwritable_or_missing_backup_dir_does_not_raise(tmp_path, caplog, fake_clock):
    db = _db(tmp_path / "genba.db")
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("x")  # フォルダの場所にファイルがある(書き込めない)
    assert make_backup(db, blocker, keep=30, reason="daily") is None
    assert make_backup(db, blocker / "sub", keep=30, reason="daily") is None
    assert make_backup(db, None, keep=30, reason="daily") is None
    assert make_backup(tmp_path / "nothing.db", tmp_path / "backup", keep=30, reason="startup") is None  # DBがまだ無い
    messages = [r.getMessage() for r in caplog.records]
    assert any("バックアップを取れませんでした" in m for m in messages)
    assert any("backup_dir が設定されていない" in m for m in messages)


def test_seconds_until_daily_time():
    at = time(12, 30)
    assert seconds_until(datetime(2026, 10, 21, 12, 0, tzinfo=JST), at) == 30 * 60
    assert seconds_until(datetime(2026, 10, 21, 12, 30, tzinfo=JST), at) == 24 * 3600  # ちょうどなら翌日
    assert seconds_until(datetime(2026, 10, 21, 13, 0, tzinfo=JST), at) == 23.5 * 3600


def test_startup_backup_is_taken_before_migration(tmp_path, monkeypatch, fake_clock):
    db = _db(tmp_path / "api.db")  # 前の版のDB(マイグレーションの前の形)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        f'[paths]\ndatabase = "{db.as_posix()}"\nbackup_dir = "{(tmp_path / "backup").as_posix()}"\n[backup]\nkeep = 5\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GENBA_CONFIG", str(cfg))
    from app.core.config import get_config

    get_config.cache_clear()
    from app.main import app

    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
    finally:
        get_config.cache_clear()
    [saved] = (tmp_path / "backup").iterdir()
    assert saved.name.endswith("_startup.db")
    with closing(sqlite3.connect(saved)) as c:  # マイグレーションの前の中身(alembic_version が無い)
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"t"}
