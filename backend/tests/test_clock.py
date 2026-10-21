"""テスト用の時計(GENBA_CLOCK_START)の歯止め。"""

from datetime import datetime

import pytest

from app.core.clock import JST, resolve_test_clock_start

START = "2026-10-21T10:00:00+09:00"


def test_enabled_only_with_both_settings(caplog):
    assert resolve_test_clock_start({"GENBA_CLOCK_START": START, "GENBA_TEST_MODE": "1"}, frozen=False) == datetime(
        2026, 10, 21, 10, 0, tzinfo=JST,
    )
    assert "テスト用の時計を使います" in caplog.text


@pytest.mark.parametrize(
    "env",
    [
        {"GENBA_CLOCK_START": START},  # GENBA_TEST_MODE が無い
        {"GENBA_CLOCK_START": START, "GENBA_TEST_MODE": "0"},
        {"GENBA_CLOCK_START": START, "GENBA_TEST_MODE": "true"},  # 1 以外は認めない
        {"GENBA_TEST_MODE": "1"},  # GENBA_CLOCK_START が無い
    ],
)
def test_ignored_with_only_one_setting(env, caplog):
    assert resolve_test_clock_start(env, frozen=False) is None
    assert "片方だけ" in caplog.text


def test_always_disabled_in_exe(caplog):
    assert resolve_test_clock_start({"GENBA_CLOCK_START": START, "GENBA_TEST_MODE": "1"}, frozen=True) is None
    assert "exe では" in caplog.text


def test_nothing_set_is_silent(caplog):
    assert resolve_test_clock_start({}, frozen=False) is None
    assert resolve_test_clock_start({}, frozen=True) is None
    assert caplog.text == ""
