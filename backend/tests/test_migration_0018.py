"""マイグレーション 0018(side_links を広げる、書き出した行の記録)。古い確定の行の読み替えと、古い書き出しからの記録。"""

from alembic import command
from sqlalchemy import text

from app.db.migrate import alembic_config
from app.db.session import make_engine

T = "'2026-10-21 09:00:00.000000'"
CSV = ("書式版,書き出し日時,元のDB(フォルダ名),キッティングNo.,ロットNo.,ファイルNo.,面,日付,生産数(累計),NG面1,NG面2,担当者ID,面1のキッティングNo.\r\n"
       "2,2026-10-21 10:00:00,2026-10,K2,L001,0722,2,2026-10-21,300,0,0,Y001,K1\r\n"
       "2,2026-10-21 10:00:00,2026-10,K3,L009,0800,1,2026-10-21,50,0,0,Y001,\r\n")


def test_old_rows_are_read_as_link_or_skip_and_old_exports_are_recorded(tmp_path):
    e = make_engine(tmp_path / "old.db")
    cfg = alembic_config()
    with e.begin() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "0017")
        c.execute(text("INSERT INTO operators (name, active, sort_order) VALUES ('管理', 1, 1)"))
        c.execute(text("INSERT INTO side_links (lot_no, side1_kitting_no, side2_kitting_no, decided_by, decided_at) "
                       f"VALUES ('L001', 'K1', 'K2', 1, {T}), ('L001', 'K1', NULL, 1, {T})"))
        c.execute(text("INSERT INTO actuals_exports (exported_at, exported_by, row_count, file_name, date_from, date_to, content) "
                       f"VALUES ({T}, 1, 2, 'a.csv', '2026-10-21', '2026-10-21', :content)"), {"content": CSV})
        command.upgrade(cfg, "0018")
        links = c.execute(text("SELECT action, source, side2_kitting_no FROM side_links ORDER BY id")).all()
        rows = c.execute(text("SELECT kitting_no, lot_no, side1_kitting_no FROM exported_rows ORDER BY id")).all()
    assert [tuple(r) for r in links] == [("link", "admin", "K2"), ("skip", "admin", None)]  # つなぐ / つながない(管理者)
    assert [tuple(r) for r in rows] == [("K2", "L001", "K1"), ("K3", "L009", None)]
