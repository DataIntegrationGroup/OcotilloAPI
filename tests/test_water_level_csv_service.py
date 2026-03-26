from datetime import date

from db import Thing
from db.measuring_point_history import MeasuringPointHistory
from services.water_level_csv import (
    _resolve_measuring_point_height,
    _validate_depth_to_water_against_well,
)


def _build_well(
    *,
    well_depth: float | None = None,
    measuring_point_height: float | None = None,
) -> Thing:
    well = Thing(name="AR0001", thing_type="water well", well_depth=well_depth)
    well.measuring_points = []
    if measuring_point_height is not None:
        well.measuring_points.append(
            MeasuringPointHistory(
                start_date=date(2025, 1, 1),
                measuring_point_height=measuring_point_height,
            )
        )
    return well


def test_resolve_measuring_point_height_prefers_csv_value():
    well = _build_well(measuring_point_height=3.5)

    (
        resolved_mp_height,
        existing_mp_height,
        differs,
    ) = _resolve_measuring_point_height(well, 4.0)

    assert resolved_mp_height == 4.0
    assert existing_mp_height == 3.5
    assert differs is True


def test_resolve_measuring_point_height_falls_back_to_well_history():
    well = _build_well(measuring_point_height=3.5)

    (
        resolved_mp_height,
        existing_mp_height,
        differs,
    ) = _resolve_measuring_point_height(well, None)

    assert resolved_mp_height == 3.5
    assert existing_mp_height == 3.5
    assert differs is False


def test_resolve_measuring_point_height_allows_missing_values():
    well = _build_well()

    (
        resolved_mp_height,
        existing_mp_height,
        differs,
    ) = _resolve_measuring_point_height(well, None)

    assert resolved_mp_height is None
    assert existing_mp_height is None
    assert differs is False


def test_validate_depth_to_water_against_well_rejects_depth_past_bottom():
    well = _build_well(well_depth=10.0)

    error = _validate_depth_to_water_against_well(4, well, 12.5, 1.0)

    assert (
        error == "Row 4: depth_to_water_ft minus measuring point height (11.5) "
        "must be less than well depth (10.0)"
    )


def test_validate_depth_to_water_against_well_skips_when_height_unavailable():
    well = _build_well(well_depth=10.0)

    error = _validate_depth_to_water_against_well(4, well, 12.5, None)

    assert error is None
