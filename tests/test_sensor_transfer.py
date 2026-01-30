import numpy as np
import pandas as pd

from transfers.sensor_transfer import _coerce_wi_mic_gain


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
