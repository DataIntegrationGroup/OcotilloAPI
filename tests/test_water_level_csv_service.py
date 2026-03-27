from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from db import FieldActivity, FieldEvent, Observation, Sample, Thing
from db.measuring_point_history import MeasuringPointHistory
from db.engine import session_ctx
from services.water_level_csv import (
    _build_sample_name,
    _resolve_measuring_point_height,
    _validate_depth_to_water_against_well,
    bulk_upload_water_levels,
)
from sqlalchemy import select


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


def test_resolve_measuring_point_height_coerces_decimal_history_value():
    well = _build_well(measuring_point_height=Decimal("3.5"))

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


def test_build_sample_name_uses_deterministic_well_inventory_style_format():
    row = SimpleNamespace(
        well=SimpleNamespace(name="AR0001"),
        measurement_dt=datetime(2025, 2, 15, 10, 30, tzinfo=timezone.utc),
    )

    assert _build_sample_name(row) == "AR0001-WL-202502151030"


def test_bulk_upload_water_levels_is_idempotent(water_well_thing):
    csv_content = "\n".join(
        [
            ",".join(
                [
                    "field_staff",
                    "well_name_point_id",
                    "field_event_date_time",
                    "measurement_date_time",
                    "sampler",
                    "sample_method",
                    "mp_height",
                    "level_status",
                    "depth_to_water_ft",
                    "data_quality",
                    "water_level_notes",
                ]
            ),
            ",".join(
                [
                    "A Lopez",
                    water_well_thing.name,
                    "2025-02-15T08:00:00-07:00",
                    "2025-02-15T10:30:00-07:00",
                    "A Lopez",
                    "electric tape",
                    "1.5",
                    "Water level not affected",
                    "7.0",
                    "Water level accurate to within two hundreths of a foot",
                    "Initial measurement",
                ]
            ),
        ]
    )

    first = bulk_upload_water_levels(csv_content.encode("utf-8"))
    second = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert first.exit_code == 0, first.payload
    assert second.exit_code == 0, second.payload
    assert (
        first.payload["water_levels"][0]["sample_id"]
        == second.payload["water_levels"][0]["sample_id"]
    )
    assert (
        first.payload["water_levels"][0]["observation_id"]
        == second.payload["water_levels"][0]["observation_id"]
    )

    with session_ctx() as session:
        samples = session.scalars(
            select(Sample)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(
                Thing.id == water_well_thing.id,
                FieldActivity.activity_type == "groundwater level",
            )
        ).all()
        observations = session.scalars(
            select(Observation)
            .join(Sample, Observation.sample_id == Sample.id)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(
                Thing.id == water_well_thing.id,
                FieldActivity.activity_type == "groundwater level",
            )
        ).all()

        assert len(samples) == 1
        assert len(observations) == 1
        assert samples[0].sample_name == "Test Well-WL-202502151730"
        assert samples[0].sample_matrix == "groundwater"
        assert observations[0].groundwater_level_reason == "Water level not affected"
        assert (
            observations[0].nma_data_quality
            == "Water level accurate to within two hundreths of a foot"
        )
        assert observations[0].measuring_point_height == 1.5


def test_bulk_upload_water_levels_imports_valid_rows_when_other_rows_fail(
    water_well_thing,
):
    csv_content = "\n".join(
        [
            ",".join(
                [
                    "field_staff",
                    "well_name_point_id",
                    "field_event_date_time",
                    "measurement_date_time",
                    "sampler",
                    "sample_method",
                    "mp_height",
                    "level_status",
                    "depth_to_water_ft",
                    "data_quality",
                    "water_level_notes",
                ]
            ),
            ",".join(
                [
                    "A Lopez",
                    water_well_thing.name,
                    "2025-02-15T08:00:00-07:00",
                    "2025-02-15T10:30:00-07:00",
                    "A Lopez",
                    "electric tape",
                    "1.5",
                    "Water level not affected",
                    "7.0",
                    "Water level accurate to within two hundreths of a foot",
                    "Initial measurement",
                ]
            ),
            ",".join(
                [
                    "A Lopez",
                    "Unknown Well",
                    "2025-02-15T08:00:00-07:00",
                    "2025-02-15T10:30:00-07:00",
                    "A Lopez",
                    "electric tape",
                    "1.5",
                    "Water level not affected",
                    "7.0",
                    "Water level accurate to within two hundreths of a foot",
                    "Bad row",
                ]
            ),
        ]
    )

    result = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert result.exit_code == 0
    assert result.payload["summary"]["total_rows_processed"] == 2
    assert result.payload["summary"]["total_rows_imported"] == 1
    assert result.payload["summary"]["validation_errors_or_warnings"] == 1
    assert len(result.payload["water_levels"]) == 1
    assert (
        "Unknown well_name_point_id 'Unknown Well'"
        in result.payload["validation_errors"][0]
    )
