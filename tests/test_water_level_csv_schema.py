from datetime import datetime, timezone

from schemas.water_level_csv import WaterLevelCsvRow


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
        data_quality="Approved",
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
        level_status="",
        depth_to_water_ft="",
        data_quality="",
        water_level_notes="",
    )

    assert row.mp_height is None
    assert row.level_status is None
    assert row.depth_to_water_ft is None
    assert row.data_quality is None
    assert row.water_level_notes is None
