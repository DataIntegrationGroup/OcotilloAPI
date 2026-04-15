from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from db import (
    Contact,
    FieldActivity,
    FieldEvent,
    FieldEventParticipant,
    Observation,
    Sample,
    Thing,
)
from db.measuring_point_history import MeasuringPointHistory
from db.engine import session_ctx
from tests import get_parameter_id
from services.water_level_csv import (
    _build_sample_name,
    _create_records,
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


def test_create_records_reports_savepoint_creation_failure_as_row_error():
    class BrokenSession:
        def __init__(self):
            self.expire_all_called = False

        def begin_nested(self):
            raise RuntimeError("savepoint failed")

        def expire_all(self):
            self.expire_all_called = True

    session = BrokenSession()

    created, errors = _create_records(
        session,
        parameter_id=1,
        rows=[SimpleNamespace(row_index=7)],
    )

    assert created == []
    assert errors == ["Row 7: savepoint failed"]
    assert session.expire_all_called is True


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
        assert samples[0].field_event_participant is not None
        assert samples[0].field_event_participant.participant.name == "A Lopez"
        assert observations[0].groundwater_level_reason == "Water level not affected"
        assert (
            observations[0].nma_data_quality
            == "Water level accurate to within two hundreths of a foot"
        )
        assert observations[0].measuring_point_height == 1.5


def test_bulk_upload_water_levels_creates_field_event_participants(water_well_thing):
    csv_content = "\n".join(
        [
            ",".join(
                [
                    "field_staff",
                    "field_staff_2",
                    "field_staff_3",
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
                    "B Chen",
                    "C Diaz",
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

    result = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert result.exit_code == 0, result.payload

    with session_ctx() as session:
        field_event = session.scalars(
            select(FieldEvent)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(Thing.id == water_well_thing.id)
        ).one()
        participants = session.scalars(
            select(FieldEventParticipant)
            .where(FieldEventParticipant.field_event_id == field_event.id)
            .order_by(FieldEventParticipant.id.asc())
        ).all()
        contacts = session.scalars(
            select(Contact)
            .where(
                Contact.name.in_(["A Lopez", "B Chen", "C Diaz"]),
                Contact.organization == "NMBGMR",
                Contact.contact_type == "Field Event Participant",
            )
            .order_by(Contact.name.asc())
        ).all()

        assert len(participants) == 3
        assert [participant.participant_role for participant in participants] == [
            "Lead",
            "Participant",
            "Participant",
        ]
        assert {participant.field_event_id for participant in participants} == {
            field_event.id
        }
        # Notes now carry only freeform text; staff identity should come from the
        # structured participant records and the sample participant link.
        assert field_event.notes == "Initial measurement"
        assert len(contacts) == 3
        field_activity = session.scalars(
            select(FieldActivity).where(FieldActivity.field_event_id == field_event.id)
        ).one()
        assert field_activity.notes is None
        sample = session.scalars(
            select(Sample)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .where(FieldActivity.field_event_id == field_event.id)
        ).one()
        assert sample.field_event_participant_id == participants[0].id
        assert sample.field_event_participant.participant.name == "A Lopez"


def test_bulk_upload_water_levels_does_not_duplicate_field_event_participants_on_rerun(
    water_well_thing,
):
    csv_content = "\n".join(
        [
            ",".join(
                [
                    "field_staff",
                    "field_staff_2",
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
                    "B Chen",
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

    assert first.exit_code == 0, first.payload

    with session_ctx() as session:
        field_event = session.scalars(
            select(FieldEvent)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(Thing.id == water_well_thing.id)
        ).one()
        participants = session.scalars(
            select(FieldEventParticipant)
            .where(FieldEventParticipant.field_event_id == field_event.id)
            .order_by(FieldEventParticipant.id.asc())
        ).all()
        sample = session.scalars(
            select(Sample)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .where(FieldActivity.field_event_id == field_event.id)
        ).one()

        # Capture the exact participant/contact linkage from the first import so
        # the rerun can prove the importer reused those records rather than
        # creating replacements.
        first_participant_ids = [participant.id for participant in participants]
        first_contact_ids = [participant.contact_id for participant in participants]
        first_sample_participant_id = sample.field_event_participant_id

    second = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert second.exit_code == 0, second.payload

    with session_ctx() as session:
        field_events = session.scalars(
            select(FieldEvent)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(Thing.id == water_well_thing.id)
        ).all()
        participants = session.scalars(
            select(FieldEventParticipant)
            .where(FieldEventParticipant.field_event_id == field_events[0].id)
            .order_by(FieldEventParticipant.id.asc())
        ).all()
        sample = session.scalars(
            select(Sample)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .where(FieldActivity.field_event_id == field_events[0].id)
        ).one()

        assert len(field_events) == 1
        assert len(participants) == 2
        assert [participant.id for participant in participants] == first_participant_ids
        assert [
            participant.contact_id for participant in participants
        ] == first_contact_ids
        assert sample.field_event_participant_id == first_sample_participant_id
        assert sample.field_event_participant is not None
        assert sample.field_event_participant.participant.name == "A Lopez"


def test_bulk_upload_water_levels_fails_when_measuring_person_is_ambiguous(
    water_well_thing,
):
    csv_content = "\n".join(
        [
            ",".join(
                [
                    "field_staff",
                    "field_staff_2",
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

    result = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert result.exit_code == 1
    assert result.payload["summary"]["total_rows_imported"] == 0
    assert result.payload["validation_errors"] == [
        "Row 1: measuring_person 'A Lopez' matched multiple field event "
        "participants; field_staff values must identify exactly one measuring "
        "person"
    ]

    with session_ctx() as session:
        samples = session.scalars(select(Sample)).all()
        participants = session.scalars(select(FieldEventParticipant)).all()

        assert samples == []
        assert participants == []


def test_bulk_upload_water_levels_warns_when_mp_height_differs_from_history(
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
                    "Measurement with warning",
                ]
            ),
        ]
    )

    result = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert result.exit_code == 0, result.payload
    assert result.payload["summary"]["total_rows_imported"] == 1
    assert result.payload["summary"]["validation_errors_or_warnings"] == 1
    assert result.payload["validation_errors"] == [
        "Row 1: CSV mp_height (1.5) differs from existing measuring point height "
        "(2.0); CSV value will be used"
    ]


def test_bulk_upload_water_levels_preserves_unrelated_existing_observations(
    water_well_thing,
):
    groundwater_parameter_id = get_parameter_id("groundwater level", "Field Parameter")
    ph_parameter_id = get_parameter_id("pH", "Field Parameter")

    with session_ctx() as session:
        well = session.merge(water_well_thing)
        field_event = FieldEvent(
            thing=well,
            event_date=datetime(2025, 2, 15, 15, 0, tzinfo=timezone.utc),
            notes="Existing field event",
        )
        field_activity = FieldActivity(
            field_event=field_event,
            activity_type="groundwater level",
            notes="Sampler: Original Sampler",
        )
        sample = Sample(
            field_activity=field_activity,
            sample_date=datetime(2025, 2, 15, 17, 30, tzinfo=timezone.utc),
            sample_name="Test Well-WL-202502151730",
            sample_matrix="groundwater",
            sample_method="Electric tape measurement (E-probe)",
            qc_type="Normal",
            notes="Existing sample",
        )
        unrelated_observation = Observation(
            sample=sample,
            observation_datetime=datetime(2025, 2, 15, 17, 30, tzinfo=timezone.utc),
            parameter_id=ph_parameter_id,
            value=7.2,
            unit="dimensionless",
            notes="Keep me as pH",
        )
        session.add_all([field_event, field_activity, sample, unrelated_observation])
        session.commit()
        unrelated_observation_id = unrelated_observation.id

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
                    "Imported groundwater level",
                ]
            ),
        ]
    )

    result = bulk_upload_water_levels(csv_content.encode("utf-8"))

    assert result.exit_code == 0, result.payload

    with session_ctx() as session:
        sample = session.scalars(
            select(Sample)
            .join(FieldActivity, Sample.field_activity_id == FieldActivity.id)
            .join(FieldEvent, FieldActivity.field_event_id == FieldEvent.id)
            .join(Thing, FieldEvent.thing_id == Thing.id)
            .where(
                Thing.id == water_well_thing.id,
                FieldActivity.activity_type == "groundwater level",
                Sample.sample_name == "Test Well-WL-202502151730",
            )
        ).one()
        observations = session.scalars(
            select(Observation)
            .where(Observation.sample_id == sample.id)
            .order_by(Observation.id.asc())
        ).all()

        assert len(observations) == 2
        assert observations[0].id == unrelated_observation_id
        assert observations[0].parameter_id == ph_parameter_id
        assert observations[0].value == 7.2
        assert observations[0].unit == "dimensionless"
        assert observations[0].notes == "Keep me as pH"

        groundwater_observations = [
            observation
            for observation in observations
            if observation.parameter_id == groundwater_parameter_id
        ]
        assert len(groundwater_observations) == 1
        assert (
            groundwater_observations[0].id
            == result.payload["water_levels"][0]["observation_id"]
        )
        assert groundwater_observations[0].value == 7.0
        assert groundwater_observations[0].unit == "ft"
        assert groundwater_observations[0].notes == "Imported groundwater level"


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
    assert result.payload["summary"]["validation_errors_or_warnings"] == 2
    assert len(result.payload["water_levels"]) == 1
    assert len(result.payload["validation_errors"]) == 2
    assert any(
        "CSV mp_height (1.5) differs from existing measuring point height (2.0)"
        in message
        for message in result.payload["validation_errors"]
    )
    assert any(
        "Unknown well_name_point_id 'Unknown Well'" in message
        for message in result.payload["validation_errors"]
    )


def test_bulk_upload_water_levels_reports_duplicate_well_name_matches():
    with session_ctx() as session:
        well_one = Thing(name="Duplicate Well", thing_type="water well")
        well_two = Thing(name="Duplicate Well", thing_type="water well")
        session.add_all([well_one, well_two])
        session.commit()
        well_one_id = well_one.id
        well_two_id = well_two.id

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
                    "Duplicate Well",
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

    try:
        result = bulk_upload_water_levels(csv_content.encode("utf-8"))

        assert result.exit_code == 1
        assert result.payload["summary"]["total_rows_processed"] == 1
        assert result.payload["summary"]["total_rows_imported"] == 0
        assert result.payload["validation_errors"] == [
            "Row 1: Multiple wells found for well_name_point_id 'Duplicate Well'"
        ]
    finally:
        with session_ctx() as session:
            for well_id in (well_one_id, well_two_id):
                well = session.get(Thing, well_id)
                if well is not None:
                    session.delete(well)
            session.commit()
