import pytest

from app.domain.normalize import normalize_mounting_line, normalize_setup_file_no


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4", "0004"),
        ("0004", "0004"),
        ("00004", "00004"),  # 4桁を超える数字はそのまま(int に変換しない)
        ("722", "0722"),
        ("t458", "T458"),
        ("４", "0004"),  # 全角数字 → 半角
        ("ｔ４５８", "T458"),  # 全角英数字 → 半角
        ("  12 ", "0012"),
        ("", ""),
        (None, ""),
        (4, "0004"),  # 数値で入っていても文字列にしてから扱う
    ],
)
def test_normalize_setup_file_no(value, expected):
    assert normalize_setup_file_no(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("s", "S"),
        (" S ", "S"),
        ("ｓ", "S"),  # 全角 → 半角
        ("Ｌ１", "L1"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_mounting_line(value, expected):
    assert normalize_mounting_line(value) == expected
