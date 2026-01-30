from transfers.sensor_transfer import _coerce_wi_mic_gain, _coerce_wi_int
import numpy as np
import pandas as pd


def test_coerce_wi_mic_gain_numeric():
    assert _coerce_wi_mic_gain(1) is True
    assert _coerce_wi_mic_gain(0) is False
    assert _coerce_wi_mic_gain(1.0) is True


def test_coerce_wi_mic_gain_strings():
    assert _coerce_wi_mic_gain("1") is True
    assert _coerce_wi_mic_gain("0") is False
    assert _coerce_wi_mic_gain(" true ") is True
    assert _coerce_wi_mic_gain("False") is False


def test_coerce_wi_mic_gain_handles_none_like():
    assert _coerce_wi_mic_gain(None) is None
    assert _coerce_wi_mic_gain("  ") is None
    assert _coerce_wi_mic_gain(pd.NA) is None
    assert _coerce_wi_mic_gain(np.nan) is None


def test_coerce_wi_int_numeric():
    assert _coerce_wi_int(1) == 1
    assert _coerce_wi_int(1.9) == 1
    assert _coerce_wi_int(0.0) == 0


def test_coerce_wi_int_strings():
    assert _coerce_wi_int("2") == 2
    assert _coerce_wi_int(" 3.0 ") == 3
    assert _coerce_wi_int("true") is None


def test_coerce_wi_int_none_like():
    assert _coerce_wi_int(None) is None
    assert _coerce_wi_int("  ") is None
    assert _coerce_wi_int(pd.NA) is None
    assert _coerce_wi_int(np.nan) is None
