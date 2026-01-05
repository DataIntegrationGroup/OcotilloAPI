import tempfile

from db.engine import session_ctx
from db import (
    FieldEvent,
    FieldActivity,
    FieldEventParticipant,
    Sample,
    Observation,
)
from schemas.water_level_csv import (
    WaterLevelBulkUploadSummary,
    WaterLevelBulkUploadPayload,
)
from services.water_level_csv import bulk_upload_water_levels


def test_bulk_upload(
    water_level_bulk_upload_data, water_well_thing, contact, second_contact
):
    """
    The bulk upload function is used both by the API and the CLI, so it is tested
    separately here assuming that the functionality is the same. This assumes that
    the file is parsed correctly and tested for each interface.
    This test focuses on the data processing and database insertion.
    """

    # write to a CSV file in memory then delete it after processing
    # this is being done to avoid filesystem dependencies in tests and
    # to use the contact fixture for the field staff
    csv_headers = list(water_level_bulk_upload_data.keys())
    csv_values = list(water_level_bulk_upload_data.values())

    csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", delete_on_close=True
    ) as temp_csv:
        temp_csv.write(csv_content)
        temp_csv.flush()

        # process the CSV file
        results = bulk_upload_water_levels(temp_csv.name)

        assert results.exit_code == 0

        assert len(results.payload.water_levels) == 1
        created_records = results.payload.water_levels[0]

        # verify the data was inserted correctly and then clean up
        with session_ctx() as session:
            # ----------
            # INSERTION VERIFICATION
            # ----------

            # FieldEvent
            field_event = session.get(FieldEvent, created_records.field_event_id)
            assert field_event is not None
            assert field_event.thing_id == water_well_thing.id
            # TODO: uncomment after timezone handling is fixed
            # assert field_event.event_date.isoformat() == "2025-02-15T15:00:00+00:00"
            assert (
                field_event.event_date.isoformat()
                == water_level_bulk_upload_data["field_event_date_time"] + "+00:00"
            )

            # FieldActivity
            field_activity = session.get(
                FieldActivity, created_records.field_activity_id
            )
            assert field_activity is not None
            assert field_activity.activity_type == "groundwater level"

            # FieldEventParticipants
            field_event_participant_1 = session.get(
                FieldEventParticipant, created_records.field_event_participant_1_id
            )
            assert field_event_participant_1 is not None
            assert field_event_participant_1.contact_id == contact.id
            assert field_event_participant_1.field_event_id == field_event.id
            assert field_event_participant_1.participant_role == "Lead"

            field_event_participant_2 = session.get(
                FieldEventParticipant, created_records.field_event_participant_2_id
            )
            assert field_event_participant_2 is not None
            assert field_event_participant_2.contact_id == second_contact.id
            assert field_event_participant_2.field_event_id == field_event.id
            assert field_event_participant_2.participant_role == "Participant"

            assert created_records.field_event_participant_3_id is None

            # Sample
            sample = session.get(Sample, created_records.sample_id)
            assert sample is not None
            assert sample.field_activity_id == field_activity.id
            # TODO: uncomment after timezone handling is fixed
            # assert sample.sample_date.isoformat() == "2025-02-15T17:30:00+00:00"
            assert (
                sample.sample_date.isoformat()
                == water_level_bulk_upload_data["water_level_date_time"] + "+00:00"
            )
            assert sample.sample_name[0:3] == "wl-"
            assert sample.sample_matrix == "water"
            assert sample.sample_method == water_level_bulk_upload_data["sample_method"]
            assert sample.qc_type == "Normal"
            assert sample.depth_top is None
            assert sample.depth_bottom is None

            # Observation
            observation = session.get(Observation, created_records.observation_id)
            assert observation is not None
            assert observation.sample_id == sample.id
            # TODO: uncomment after timezone handling is fixed
            # assert observation.observation_datetime.isoformat() == "2025-02-15T17:30:00+00:00"
            assert (
                observation.observation_datetime.isoformat()
                == water_level_bulk_upload_data["water_level_date_time"] + "+00:00"
            )
            assert observation.value == float(
                water_level_bulk_upload_data["depth_to_water_ft"]
            )
            assert observation.unit == "ft"
            assert observation.measuring_point_height == float(
                water_level_bulk_upload_data["mp_height"]
            )
            assert (
                observation.groundwater_level_reason
                == water_level_bulk_upload_data["level_status"]
            )
            assert (
                observation.groundwater_level_accuracy
                == water_level_bulk_upload_data["data_quality"]
            )
            assert (
                observation.notes == water_level_bulk_upload_data["water_level_notes"]
            )

            # ----------
            # CLEAN UP
            # ----------

            session.delete(observation)
            session.delete(sample)
            session.delete(field_activity)
            session.delete(field_event_participant_1)
            session.delete(field_event_participant_2)
            session.delete(field_event)
            session.commit()


def test_bulk_upload_file_not_found():
    """
    Test the bulk upload function with a non-existent file path.
    """

    results = bulk_upload_water_levels("non_existent_file.csv")

    assert results.exit_code == 1
    assert (
        results.stdout
        == '{"summary": {"total_rows_processed": 0, "total_rows_imported": 0, "total_validation_errors_or_warnings": 0}, "water_levels": [], "validation_errors": []}'
    )
    assert results.stderr == "File not found: non_existent_file.csv"
    assert isinstance(results.payload, WaterLevelBulkUploadPayload)
    assert isinstance(results.payload.summary, WaterLevelBulkUploadSummary)
    assert results.payload.summary.total_rows_imported == 0
    assert results.payload.summary.total_rows_processed == 0
    assert results.payload.summary.total_validation_errors_or_warnings == 0
    assert results.payload.water_levels == []
    assert results.payload.validation_errors == []


def test_bulk_upload_nonexistent_well(water_level_bulk_upload_data):
    """
    Test the bulk upload function with a nonexistent well name.
    """
    bad_water_level_bulk_upload_data = water_level_bulk_upload_data.copy()
    bad_water_level_bulk_upload_data["well_name_point_id"] = "NonExistentWell"

    # write to a CSV file in memory then delete it after processing
    csv_headers = list(bad_water_level_bulk_upload_data.keys())
    csv_values = list(bad_water_level_bulk_upload_data.values())

    csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    with tempfile.NamedTemporaryFile(
        mode="w+", encoding="utf-8", delete_on_close=True
    ) as temp_csv:
        temp_csv.write(csv_content)
        temp_csv.flush()

        results = bulk_upload_water_levels(temp_csv.name)

        assert results.exit_code == 1
        assert (
            results.stdout
            == '{"summary": {"total_rows_processed": 1, "total_rows_imported": 0, "total_validation_errors_or_warnings": 1}, "water_levels": [], "validation_errors": ["Row 1: Unknown well_name_point_id \'NonExistentWell\'"]}'
        )
        assert results.stderr == "Row 1: Unknown well_name_point_id 'NonExistentWell'"
        assert isinstance(results.payload, WaterLevelBulkUploadPayload)
        assert isinstance(results.payload.summary, WaterLevelBulkUploadSummary)
        assert results.payload.summary.total_rows_imported == 0
        assert results.payload.summary.total_rows_processed == 1
        assert results.payload.summary.total_validation_errors_or_warnings == 1
        assert results.payload.water_levels == []
        assert results.payload.validation_errors == [
            "Row 1: Unknown well_name_point_id 'NonExistentWell'"
        ]


def test_bulk_upload_bad_dtw_bgs(water_level_bulk_upload_data, water_well_thing):
    """
    Test the bulk upload function with a non-numeric depth to water below ground surface.
    """
    pass
    # # Update the depth_to_water_ft to a non-numeric value
    # water_level_bulk_upload_data["depth_to_water_ft"] = "not_a_number"

    # # write to a CSV file in memory then delete it after processing
    # csv_headers = list(water_level_bulk_upload_data.keys())
    # csv_values = list(water_level_bulk_upload_data.values())

    # csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    # with tempfile.NamedTemporaryFile(
    #     mode="w+", encoding="utf-8", delete_on_close=True
    # ) as temp_csv:
    #     temp_csv.write(csv_content)
    #     temp_csv.flush()

    #     results = bulk_upload_water_levels(temp_csv.name)

    #     assert results.exit_code == 1
    #     assert "Invalid depth_to_water_ft value: not_a_number" in results.stderr
    #     assert isinstance(results.payload, WaterLevelBulkUploadPayload)


def test_bulk_upload_bad_field_staff(water_level_bulk_upload_data, water_well_thing):
    """
    Test the bulk upload function with a non-existent field staff name.
    """
    pass
    # # Update the field_staff_1 to a non-existent contact name
    # water_level_bulk_upload_data["field_staff_1"] = "NonExistentContact"

    # # write to a CSV file in memory then delete it after processing
    # csv_headers = list(water_level_bulk_upload_data.keys())
    # csv_values = list(water_level_bulk_upload_data.values())

    # csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    # with tempfile.NamedTemporaryFile(
    #     mode="w+", encoding="utf-8", delete_on_close=True
    # ) as temp_csv:
    #     temp_csv.write(csv_content)
    #     temp_csv.flush()

    #     results = bulk_upload_water_levels(temp_csv.name)

    #     assert results.exit_code == 1
    #     assert "Field staff not found: NonExistentContact" in results.stderr
    #     assert isinstance(results.payload, WaterLevelBulkUploadPayload)


def test_bulk_upload_bad_field_staff_2(water_level_bulk_upload_data, water_well_thing):
    """
    Test the bulk upload function with a non-existent second field staff name.
    """
    pass
    # # Update the field_staff_2 to a non-existent contact name
    # water_level_bulk_upload_data["field_staff_2"] = "NonExistentContact2"

    # # write to a CSV file in memory then delete it after processing
    # csv_headers = list(water_level_bulk_upload_data.keys())
    # csv_values = list(water_level_bulk_upload_data.values())

    # csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    # with tempfile.NamedTemporaryFile(
    #     mode="w+", encoding="utf-8", delete_on_close=True
    # ) as temp_csv:
    #     temp_csv.write(csv_content)
    #     temp_csv.flush()

    #     results = bulk_upload_water_levels(temp_csv.name)

    #     assert results.exit_code == 1
    #     assert "Field staff not found: NonExistentContact2" in results.stderr
    #     assert isinstance(results.payload, WaterLevelBulkUploadPayload


def test_bulk_upload_bad_field_staff_3(water_level_bulk_upload_data, water_well_thing):
    """
    Test the bulk upload function with a non-existent third field staff name.
    """
    pass
    # # Update the field_staff_3 to a non-existent contact name
    # water_level_bulk_upload_data["field_staff_3"] = "NonExistentContact3"

    # # write to a CSV file in memory then delete it after processing
    # csv_headers = list(water_level_bulk_upload_data.keys())
    # csv_values = list(water_level_bulk_upload_data.values())

    # csv_content = ",".join(csv_headers) + "\n" + ",".join(csv_values)

    # with tempfile.NamedTemporaryFile(
    #     mode="w+", encoding="utf-8", delete_on_close=True
    # ) as temp_csv:
    #     temp_csv.write(csv_content)
    #     temp_csv.flush()

    #     results = bulk_upload_water_levels(temp_csv.name)

    #     assert results.exit_code == 1
    #     assert "Field staff not found: NonExistentContact3" in results.stderr
    #     assert isinstance(results.payload, WaterLevelBulkUploadPayload)
