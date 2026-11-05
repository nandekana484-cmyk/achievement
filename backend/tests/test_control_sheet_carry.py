"""Excel の取り込みで、工程名のベトナム語と「対応」を、今の内容の同じ工程名の行から引き継ぐ(AD-28)。"""

from app.services.control_sheet_carry import carry_over, match_rows
from app.services.control_sheets import ControlRow


def cur(name, vi=None, link="none", procedure=""):
    return ControlRow(name=name, name_vi=vi, link=link, procedure=procedure)


def new(name, procedure="新"):
    return ControlRow(name=name, procedure=procedure)


def test_same_position_and_name_carries_vi_and_link():
    r = carry_over([cur("SMT-1", "Reflow", "run1"), cur("X線", "X-quang", "xray")], [new("SMT-1"), new("X線")])
    assert [(x.name, x.name_vi, x.link, x.procedure) for x in r.rows] == [("SMT-1", "Reflow", "run1", "新"), ("X線", "X-quang", "xray", "新")]  # 作業要領などは新しい内容のまま
    assert (r.carried, r.lost) == (2, [])


def test_shifted_position_is_matched_by_a_unique_name():
    r = carry_over([cur("A", "a", "run1"), cur("B", "b", "run2")], [new("前に足した行"), new("B"), new("A")])  # 位置がずれても、工程名が1つずつなら合わせる
    assert [(x.name, x.name_vi, x.link) for x in r.rows] == [("前に足した行", None, "none"), ("B", "b", "run2"), ("A", "a", "run1")]
    assert r.carried == 2 and r.lost == []


def test_same_position_is_matched_first():
    r = carry_over([cur("検査", "vi1", "run1"), cur("検査", "vi2", "xray")], [new("検査"), new("検査")])  # 同じ工程名が2つでも、同じ位置どうしは合わせる
    assert [(x.name_vi, x.link) for x in r.rows] == [("vi1", "run1"), ("vi2", "xray")]


def test_two_same_names_in_remaining_rows_are_not_guessed():
    # 位置がずれていて、同じ工程名が2つ(今の内容にも新しい内容にも)。どちらと合わせるか決められないので、引き継がない
    r = carry_over([cur("先頭"), cur("検査", "vi1", "run1"), cur("検査", "vi2", "xray")], [new("先頭"), new("別"), new("別2"), new("検査"), new("検査")])
    assert [x.name_vi for x in r.rows] == [None] * 5
    assert r.carried == 0
    assert [(x.row, x.name, x.name_vi) for x in r.lost] == [(2, "検査", "vi1"), (3, "検査", "vi2")]  # 消えるものとして出す


def test_one_remaining_name_on_each_side_matches_even_if_others_are_duplicated_elsewhere():
    r = carry_over([cur("検査", "v1"), cur("検査", "v2"), cur("単独", "s", "run2")], [new("検査"), new("検査"), new("間"), new("単独")])
    assert r.rows[3].name_vi == "s" and r.rows[3].link == "run2"  # 位置が違っても、残りで1つずつ
    assert [x.name_vi for x in r.rows[:2]] == ["v1", "v2"]  # 同じ位置の検査どうし


def test_changed_name_loses_vi_and_link():
    r = carry_over([cur("SMT-1", "Reflow", "run1"), cur("旧名", "vi", "xray"), cur("付けていない")], [new("SMT-1"), new("新名")])
    assert [x.name_vi for x in r.rows] == ["Reflow", None]
    assert r.carried == 1
    assert [(x.row, x.name, x.name_vi, x.link) for x in r.lost] == [(2, "旧名", "vi", "xray")]  # ベトナム語も対応も無い行は出さない


def test_empty_name_rows_are_never_carried():
    r = carry_over([cur("", "vi", "run1"), cur("A", "a")], [new(""), new("A")])
    assert [(x.name_vi, x.link) for x in r.rows] == [(None, "none"), ("a", "none")]
    assert match_rows([cur("")], [new("")]) == {}
    assert [(x.row, x.name_vi) for x in r.lost] == [(1, "vi")]  # 空の行のベトナム語・対応は消える


def test_nothing_to_carry_from_an_empty_current():
    r = carry_over([], [new("A"), new("B")])
    assert (r.carried, r.lost) == (0, []) and [x.name for x in r.rows] == ["A", "B"]
