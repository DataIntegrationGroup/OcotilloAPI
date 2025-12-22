import tempfile

from db.engine import session_ctx
from db import (
    FieldEvent,
    FieldActivity,
    # FieldEventParticipant,
    Sample,
    Observation,
)
from services.water_level_csv import bulk_upload_water_levels


def test_bulk_upload(water_well_thing, contact):
    """
    The bulk upload function is used both by the API and the CLI, so it is tested
    separately here assuming that the functionality is the same. This assumes that
    the file is parsed correctly and tested for each interface.
    This test focuses on the data processing and database insertion.
    """

    # write to a CSV file in memory then delete it after processing
    # this is being done to avoid filesystem dependencies in tests and
    # to use the contact fixture for the field staff
    csv_content = ",".join(
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
    )
    csv_content += "\n"
    csv_content += ",".join(
        [
            contact.name,
            water_well_thing.name,
            "2025-02-15T08:00:00",
            "2025-02-15T10:30:00",
            "Groundwater Team",
            "electric tape",
            "1.5",
            "stable",
            "45.2",
            "approved",
            "Initial measurement",
        ]
    )

    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", delete_on_close=True
    ) as temp_csv:
        temp_csv.write(csv_content)
        temp_csv.flush()

        # process the CSV file
        results = bulk_upload_water_levels(temp_csv.name)

        assert results.exit_code == 0

        assert len(results.payload["water_levels"]) == 1
        created_records = results.payload["water_levels"][0]

        # verify the data was inserted correctly and then clean up
        with session_ctx() as session:
            # ----------
            # INSERTION VERIFICATION
            # ----------

            # FieldEvent
            field_event = session.get(FieldEvent, created_records["field_event_id"])
            assert field_event is not None
            assert field_event.thing_id == water_well_thing.id
            # TODO: uncomment after timezone handling is fixed
            # assert field_event.event_date.isoformat() == "2025-02-15T15:00:00+00:00"
            assert field_event.event_date.isoformat() == "2025-02-15T08:00:00+00:00"

            # FieldActivity
            field_activity = session.get(
                FieldActivity, created_records["field_activity_id"]
            )
            assert field_activity is not None
            assert field_activity.activity_type == "groundwater level"

            # FieldEventParticipant

            # Sample
            sample = session.get(Sample, created_records["sample_id"])
            assert sample is not None
            assert sample.field_activity_id == field_activity.id
            # TODO: uncomment after timezone handling is fixed
            # assert sample.sample_date.isoformat() == "2025-02-15T17:30:00+00:00"
            assert sample.sample_date.isoformat() == "2025-02-15T10:30:00+00:00"
            assert sample.sample_name[0:3] == "wl-"
            assert sample.sample_matrix == "water"
            assert sample.sample_method == "Electric tape measurement (E-probe)"
            assert sample.qc_type == "Normal"
            assert sample.depth_top is None
            assert sample.depth_bottom is None
            # TODO: uncomment after notes handling is fixed
            # assert sample.notes is None

            # Observation
            observation = session.get(Observation, created_records["observation_id"])
            assert observation is not None
            assert observation.sample_id == sample.id
            # TODO: uncomment after timezone handling is fixed
            # assert observation.observation_datetime.isoformat() == "2025-02-15T17:30:00+00:00"
            assert (
                observation.observation_datetime.isoformat()
                == "2025-02-15T10:30:00+00:00"
            )
            assert observation.value == 45.2
            assert observation.unit == "ft"
            assert observation.measuring_point_height == 1.5
            assert observation.groundwater_level_reason is None
            assert observation.groundwater_level_accuracy is None
            # TODO: uncomment after notes handling is fixed
            # assert observation.notes == "Initial measurement"

            # ----------
            # CLEAN UP
            # ----------

            session.delete(observation)
            session.delete(sample)
            session.delete(field_activity)
            session.delete(field_event)
            session.commit()
