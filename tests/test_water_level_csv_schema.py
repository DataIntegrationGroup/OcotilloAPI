from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.water_level_csv import WaterLevelCsvRow

DATA_QUALITY_VALUE = "Water level accurate to within two hundreths of a foot"


def test_water_level_csv_row_normalizes_source_headers_and_naive_datetimes():
    row = WaterLevelCsvRow(
        well_name_point_id="AR0001",
        field_event_date_time="2025-02-15T08:00:00",
        field_staff="Tech 1",
        field_staff_2="",
        field_staff_3="",
        water_level_date_time="2025-02-15T10:30:00",
        measuring_person="Tech 1",
        sample_method="electric tape",
        mp_height="1.5",
        level_status="Water level not affected",
        depth_to_water_ft="45.2",
        data_quality=DATA_QUALITY_VALUE,
        water_level_notes="Initial measurement",
    )

    assert row.field_staff_2 is None
    assert row.field_staff_3 is None
    assert row.sample_method == "Electric tape measurement (E-probe)"
    assert row.field_event_date_time == datetime(
        2025, 2, 15, 15, 0, tzinfo=timezone.utc
    )
    assert row.water_level_date_time == datetime(
        2025, 2, 15, 17, 30, tzinfo=timezone.utc
    )


def test_water_level_csv_row_accepts_legacy_alias_headers():
    row = WaterLevelCsvRow(
        well_name_point_id="AR0001",
        field_event_date_time="2025-02-15T08:00:00-07:00",
        field_staff="Tech 1",
        measurement_date_time="2025-02-15T10:30:00-07:00",
        sampler="Tech 1",
        sample_method="Steel-tape measurement",
        mp_height_ft="2.5",
        depth_to_water_ft="45.2",
    )

    assert row.measuring_person == "Tech 1"
    assert row.sampler == "Tech 1"
    assert row.mp_height == 2.5
    assert row.measurement_date_time == datetime(
        2025, 2, 15, 17, 30, tzinfo=timezone.utc
    )


def test_water_level_csv_row_normalizes_blank_optional_values_to_none():
    row = WaterLevelCsvRow(
        well_name_point_id="AR0001",
        field_event_date_time="2025-02-15T08:00:00",
        field_staff="Tech 1",
        water_level_date_time="2025-02-15T10:30:00",
        measuring_person="Tech 1",
        sample_method="Steel-tape measurement",
        mp_height="",
        level_status="Water level not affected",
        depth_to_water_ft="",
        data_quality="",
        water_level_notes="",
    )

    assert row.mp_height is None
    assert row.level_status == "Water level not affected"
    assert row.depth_to_water_ft is None
    assert row.data_quality is None
    assert row.water_level_notes is None


def test_water_level_csv_row_requires_measuring_person_to_match_field_staff():
    with pytest.raises(ValidationError) as exc:
        WaterLevelCsvRow(
            well_name_point_id="AR0001",
            field_event_date_time="2025-02-15T08:00:00",
            field_staff="Tech 1",
            field_staff_2="Tech 2",
            water_level_date_time="2025-02-15T10:30:00",
            measuring_person="Tech 3",
            sample_method="Steel-tape measurement",
            depth_to_water_ft="45.2",
        )

    assert (
        "measuring_person must match one of field_staff, field_staff_2, "
        "or field_staff_3"
    ) in str(exc.value)


def test_water_level_csv_row_requires_level_status_when_depth_is_blank():
    with pytest.raises(ValidationError) as exc:
        WaterLevelCsvRow(
            well_name_point_id="AR0001",
            field_event_date_time="2025-02-15T08:00:00",
            field_staff="Tech 1",
            water_level_date_time="2025-02-15T10:30:00",
            measuring_person="Tech 1",
            sample_method="Steel-tape measurement",
            depth_to_water_ft="",
            level_status="",
        )

    assert "level_status is required when depth_to_water_ft is blank" in str(exc.value)


def test_water_level_csv_row_rejects_water_level_before_field_event():
    with pytest.raises(ValidationError) as exc:
        WaterLevelCsvRow(
            well_name_point_id="AR0001",
            field_event_date_time="2025-02-15T10:30:00",
            field_staff="Tech 1",
            water_level_date_time="2025-02-15T08:00:00",
            measuring_person="Tech 1",
            sample_method="Steel-tape measurement",
            depth_to_water_ft="45.2",
        )

    assert (
        "water_level_date_time must be greater than or equal to "
        "field_event_date_time"
    ) in str(exc.value)


def test_water_level_csv_row_canonicalizes_case_insensitive_lexicon_values():
    row = WaterLevelCsvRow(
        well_name_point_id="AR0001",
        field_event_date_time="2025-02-15T08:00:00",
        field_staff="Tech 1",
        water_level_date_time="2025-02-15T10:30:00",
        measuring_person="Tech 1",
        sample_method="electric tape measurement (e-probe)",
        depth_to_water_ft="",
        level_status="dry",
        data_quality=DATA_QUALITY_VALUE.lower(),
    )

    assert row.sample_method == "Electric tape measurement (E-probe)"
    assert row.level_status == "Site was dry"
    assert row.data_quality == DATA_QUALITY_VALUE


def test_water_level_csv_row_allows_negative_mp_height():
    row = WaterLevelCsvRow(
        well_name_point_id="AR0001",
        field_event_date_time="2025-02-15T08:00:00",
        field_staff="Tech 1",
        water_level_date_time="2025-02-15T10:30:00",
        measuring_person="Tech 1",
        sample_method="Steel-tape measurement",
        mp_height="-0.1",
        depth_to_water_ft="45.2",
    )

    assert row.mp_height == -0.1


def test_water_level_csv_row_rejects_negative_depth_to_water():
    with pytest.raises(ValidationError) as exc:
        WaterLevelCsvRow(
            well_name_point_id="AR0001",
            field_event_date_time="2025-02-15T08:00:00",
            field_staff="Tech 1",
            water_level_date_time="2025-02-15T10:30:00",
            measuring_person="Tech 1",
            sample_method="Steel-tape measurement",
            depth_to_water_ft="-0.1",
        )

    assert "depth_to_water_ft must be greater than or equal to 0" in str(exc.value)
