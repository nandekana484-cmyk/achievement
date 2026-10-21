from dataclasses import replace

from app.integration.legacy_plans import read_active_plans
from app.services.plan_diff import diff_plans
from legacy_fixture import TAKT, insert_plan, make_plan_db


def _plans(tmp_path, specs):
    p = tmp_path / "plan.db"
    make_plan_db(p)
    for s in specs:
        insert_plan(p, **s)
    return {pl.key: pl for pl in read_active_plans(p, TAKT).plans}


def test_reimport_with_same_content_is_unchanged(tmp_path):
    cur = _plans(tmp_path, [{"kitting_no": "0722-1-S-251014-01"}])
    # 既存アプリは同じ内容でも版を上げる → 版だけ違っても「変化なし」
    incoming = [replace(p, legacy_version=p.legacy_version + 1, legacy_plan_item_id=99) for p in cur.values()]
    d = diff_plans(cur, incoming, set())
    assert d.unchanged == list(cur) and not d.changed and not d.added


def test_added_changed_removed(tmp_path):
    cur = _plans(tmp_path, [
        {"kitting_no": "0722-1-S-251014-01"},
        {"kitting_no": "0722-2-S-251014-02", "side": "2"},
    ])
    k1, k2 = list(cur)
    moved = replace(cur[k1], planned_start=None)
    new = replace(cur[k1], kitting_no="0800-1-S-251014-03", file_no="0800")
    d = diff_plans(cur, [moved, new], keys_with_actuals=set())
    assert [p.key for p in d.changed] == [k1]
    assert [p.key for p in d.added] == [new.key]
    assert d.removed_without_actuals == [k2]


def test_delete_flag_is_ignored(tmp_path):
    cur = _plans(tmp_path, [{"kitting_no": "0722-1-S-251014-01"}])
    flagged = [replace(p, delete_flag=True) for p in cur.values()]
    d = diff_plans(cur, flagged, keys_with_actuals=set(cur))
    assert d.unchanged == list(cur) and not d.removed_with_actuals and not d.changed


def test_takt_change_counts_as_changed(tmp_path):
    cur = _plans(tmp_path, [{"kitting_no": "0722-1-S-251014-01"}])
    retimed = [replace(p, takt_sec=31.5) for p in cur.values()]
    d = diff_plans(cur, retimed, keys_with_actuals=set())
    assert [p.key for p in d.changed] == list(cur)


def test_renumbered_plan_with_actuals_becomes_carryover(tmp_path):
    cur = _plans(tmp_path, [{"kitting_no": "0722-1-S-251014-01", "qty": 300}])
    old_key = next(iter(cur))
    # 数量の変更でキッティングNo.が振り直された
    renumbered = replace(cur[old_key], kitting_no="0722-1-S-251020-05", planned_qty=250)
    d = diff_plans(cur, [renumbered], keys_with_actuals={old_key})
    assert d.removed_with_actuals == [old_key]
    assert len(d.carryovers) == 1
    c = d.carryovers[0]
    assert c.is_unique and c.new_keys == (renumbered.key,)


def test_carryover_ignores_other_run(tmp_path):
    cur = _plans(tmp_path, [{"kitting_no": "0722-1-S-251014-01"}])
    old_key = next(iter(cur))
    other_run = replace(cur[old_key], kitting_no="0722-2-S-251020-05", run_no=2)
    d = diff_plans(cur, [other_run], keys_with_actuals={old_key})
    assert d.carryovers == []
