"""作業者IDの正規化(全角・半角と大文字・小文字の違いを無視する)。"""

import pytest

from app.domain.worker_id import worker_key


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Y001", "y001"),
        ("y001", "y001"),
        ("Ｙ００１", "y001"),  # 全角 → 半角
        ("ｙ００１", "y001"),
        ("  Y001 ", "y001"),  # 前後の空白を除く
        ("　Y001　", "y001"),  # 全角の空白も
        ("AB-01", "ab-01"),
        ("ＡＢ－０１", "ab-01"),
        ("", ""),
        (None, ""),
    ],
)
def test_worker_key(raw, key):
    assert worker_key(raw) == key


def test_inner_spaces_are_kept():
    assert worker_key("Y 001") != worker_key("Y001")
