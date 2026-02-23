from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from services.util import convert_ft_to_m, convert_m_to_ft
from transfers.util import MeasuringPointEstimator


def test_convert_ft_to_m():
    assert convert_ft_to_m(0) == 0.0
    assert convert_ft_to_m(3.28084) == 1.0
    assert convert_ft_to_m(10) == 3.048
    assert convert_ft_to_m(None) is None
    assert convert_ft_to_m(10, ndigits=4) == 3.048


def test_convert_m_to_ft():
    assert convert_m_to_ft(0) == 0.0
    assert convert_m_to_ft(1) == 3.28084
    assert convert_m_to_ft(3.048) == 10.0
    assert convert_m_to_ft(None) is None
    assert convert_m_to_ft(3.048, ndigits=4) == 10.0


def test_measuring_point_estimator_groups_sorted(monkeypatch):
    monkeypatch.setattr(
        "transfers.util.read_csv", lambda name: _mock_waterlevels_df().copy()
    )
    estimator = MeasuringPointEstimator()

    group_a = estimator._grouped.get_group("A")
    assert group_a["DateMeasured"].tolist() == [
        datetime(2024, 1, 1),
        datetime(2024, 1, 3),
    ]

    group_b = estimator._grouped.get_group("B")
    assert group_b["DateMeasured"].tolist() == [datetime(2023, 12, 1)]


def test_measuring_point_estimator_handles_missing_point(monkeypatch):
    monkeypatch.setattr(
        "transfers.util.read_csv", lambda name: _mock_waterlevels_df().copy()
    )
    estimator = MeasuringPointEstimator()
    row = SimpleNamespace(PointID="C", MPHeight=None, MeasuringPoint=None)

    mphs, mph_descs, start_dates, end_dates = estimator.estimate_measuring_point_height(
        row
    )

    assert mphs == []
    assert mph_descs == []


def test_measuring_point_estimator_rounds_estimated_height_to_two_sig_figs(monkeypatch):
    monkeypatch.setattr(
        "transfers.util.read_csv", lambda name: _mock_waterlevels_df().copy()
    )
    estimator = MeasuringPointEstimator()
    row = SimpleNamespace(PointID="A", MPHeight=None, MeasuringPoint=None)

    mphs, _, _, _ = estimator.estimate_measuring_point_height(row)

    assert mphs[0] == 1.2


def test_measuring_point_estimator_keeps_explicit_height_unrounded(monkeypatch):
    monkeypatch.setattr(
        "transfers.util.read_csv", lambda name: _mock_waterlevels_df().copy()
    )
    estimator = MeasuringPointEstimator()
    row = SimpleNamespace(PointID="A", MPHeight=1.234, MeasuringPoint="top of casing")

    mphs, _, _, _ = estimator.estimate_measuring_point_height(row)

    assert mphs == [1.234]


def _mock_waterlevels_df():
    return pd.DataFrame(
        {
            "PointID": ["A", "A", "B"],
            "DateMeasured": [
                "2024-01-03",
                "2024-01-01",
                "2023-12-01",
            ],
            "DepthToWater": [10.0, 11.234, 5.0],
            "DepthToWaterBGS": [9.0, 10.0, 4.5],
        }
    )
