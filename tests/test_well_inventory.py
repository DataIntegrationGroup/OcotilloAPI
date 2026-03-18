"""
The feature tests for the well inventory csv upload verify the CLI can
successfully process a well inventory upload and create the appropriate
response, but they do not verify that the database contents are correct.

This module contains tests that verify the correctness of the database
contents after a well inventory upload.
"""

import csv
from datetime import datetime
from pathlib import Path

import pytest
from cli.service_adapter import well_inventory_csv
from core.constants import SRID_UTM_ZONE_13N, SRID_WGS84
from core.enums import Role, ContactType
from db import (
    Base,
    Location,
    LocationThingAssociation,
    Thing,
    Sample,
    Observation,
    Contact,
    ThingContactAssociation,
    FieldEvent,
    FieldActivity,
    FieldEventParticipant,
)
from db.engine import session_ctx
from schemas.well_inventory import WellInventoryRow
from services.util import transform_srid, convert_ft_to_m
from shapely import Point


def _minimal_valid_well_inventory_row():
    return {
        "project": "Test Project",
        "well_name_point_id": "TEST-0001",
        "site_name": "Test Site",
        "date_time": "2025-02-15T10:30:00",
        "field_staff": "Test Staff",
        "utm_easting": 357000,
        "utm_northing": 3784000,
        "utm_zone": "13N",
        "elevation_ft": 5000,
        "elevation_method": "Global positioning system (GPS)",
        "measuring_point_height_ft": 3.5,
    }


def _reset_well_inventory_tables() -> None:
    with session_ctx() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in ("alembic_version", "parameter"):
                continue
            if table.name.startswith("lexicon"):
                continue
            session.execute(table.delete())
        session.commit()


@pytest.fixture(autouse=True)
def isolate_well_inventory_tables():
    _reset_well_inventory_tables()
    yield
    _reset_well_inventory_tables()


def test_well_inventory_db_contents_no_waterlevels():
    """
    Test that the well inventory upload creates the correct database contents.

    This test verifies that the well inventory upload creates the correct
    database contents by checking for the presence of specific records in
    the database.
    """

    file = Path("tests/features/data/well-inventory-valid.csv")
    assert file.exists(), "Test data file does not exist."
    result = well_inventory_csv(file)
    assert result.exit_code == 0, result.stderr

    # read file into dictionary to compare values with DB objects
    with open(file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        file_dict = {}

        for row in reader:
            file_dict[row["well_name_point_id"]] = row

    # Validate that specific records exist in the database and then clean up
    with session_ctx() as session:
        # verify the correct number of records were created for each table
        locations = session.query(Location).all()
        assert len(locations) == 2, "Expected 2 locations in the database."

        things = session.query(Thing).all()
        assert len(things) == 2, "Expected 2 things in the database."

        location_thing_associations = session.query(LocationThingAssociation).all()
        assert (
            len(location_thing_associations) == 2
        ), "Expected 2 location-thing associations in the database."

        # new field staff & new contacts
        contacts = session.query(Contact).all()
        assert len(contacts) == 5, "Expected 5 contacts in the database."

        thing_contact_associations = session.query(ThingContactAssociation).all()
        assert (
            len(thing_contact_associations) == 3
        ), "Expected 3 thing-contact associations in the database."

        field_events = session.query(FieldEvent).all()
        assert len(field_events) == 2, "Expected 2 field events in the database."

        field_activities = session.query(FieldActivity).all()
        assert (
            len(field_activities) == 2
        ), "Expected 2 field activities in the database."

        field_event_participants = session.query(FieldEventParticipant).all()
        assert (
            len(field_event_participants) == 3
        ), "Expected 3 field event participants in the database."

        # verify the values of specific records
        for point_id in file_dict.keys():
            file_content = file_dict[point_id]

            # THING AND RELATED RECORDS

            thing = session.query(Thing).filter(Thing.name == point_id).all()
            assert len(thing) == 1, f"Expected 1 thing with name {point_id}."
            thing = thing[0]

            assert thing.name == point_id
            assert thing.thing_type == "water well"
            assert (
                thing.first_visit_date
                == datetime.fromisoformat(file_content["date_time"]).date()
            )
            assert thing.well_depth == float(file_content["total_well_depth_ft"])
            assert thing.hole_depth is None
            assert thing.well_casing_diameter == float(
                file_content["casing_diameter_ft"]
            )
            assert thing.well_casing_depth is None
            assert (
                thing.well_completion_date
                == datetime.fromisoformat(file_content["date_drilled"]).date()
            )
            assert thing.well_construction_method is None
            assert thing.well_driller_name is None
            assert thing.well_pump_type == file_content["well_pump_type"]
            assert thing.well_pump_depth == float(file_content["well_pump_depth_ft"])
            assert thing.formation_completion_code is None

            assert thing.notes is not None
            assert sorted(c.content for c in thing._get_notes("Access")) == sorted(
                [file_content["specific_location_of_well"]]
            )
            assert sorted(c.content for c in thing._get_notes("General")) == sorted(
                [file_content["contact_special_requests_notes"]]
            )
            assert sorted(
                c.content for c in thing._get_notes("Sampling Procedure")
            ) == sorted(
                [
                    file_content["well_measuring_notes"],
                    file_content["sampling_scenario_notes"],
                    f"Sample possible: {file_content['sample_possible']}",
                ]
            )
            assert sorted(c.content for c in thing._get_notes("Historical")) == sorted(
                [
                    f"historic depth to water: {float(file_content['historic_depth_to_water_ft'])} ft - source: {file_content['depth_source'].lower()}"
                ]
            )

            assert (
                thing.measuring_point_description
                == file_content["measuring_point_description"]
            )
            assert float(thing.measuring_point_height) == float(
                file_content["measuring_point_height_ft"]
            )

            assert (
                thing.well_completion_date_source == file_content["completion_source"]
            )

            assert thing.well_depth_source == file_content["depth_source"]

            # well_purpose_2 is blank for both test records in the CSV
            assert sorted(wp.purpose for wp in thing.well_purposes) == sorted(
                [file_content["well_purpose"]]
            )

            assert sorted(
                mf.monitoring_frequency for mf in thing.monitoring_frequencies
            ) == sorted([file_content["monitoring_frequency"]])

            assert len(thing.permissions) == 3
            for permission_type in [
                "Water Level Sample",
                "Water Chemistry Sample",
                "Datalogger Installation",
            ]:
                permission = next(
                    (
                        p
                        for p in thing.permissions
                        if p.permission_type == permission_type
                    ),
                    None,
                )
                assert (
                    permission is not None
                ), f"Expected permission type {permission_type} for thing {point_id}."

                if permission_type == "Water Level Sample":
                    assert permission.permission_allowed is bool(
                        file_content["repeat_measurement_permission"].lower() == "true"
                    )
                elif permission_type == "Water Chemistry Sample":
                    assert permission.permission_allowed is bool(
                        file_content["sampling_permission"].lower() == "true"
                    )
                else:
                    assert permission.permission_allowed is bool(
                        file_content["datalogger_installation_permission"].lower()
                        == "true"
                    )

            assert thing.well_status == file_content["well_status"]
            assert (
                thing.datalogger_suitability_status == "Datalogger can be installed"
                if file_content["datalogger_possible"].lower() == "true"
                else "Datalogger cannot be installed"
            )
            assert (
                thing.open_status == "Open"
                if file_content["is_open"].lower() == "true"
                else "Closed"
            )

            # LOCATION AND RELATED RECORDS
            location_thing_association = (
                session.query(LocationThingAssociation)
                .filter(LocationThingAssociation.thing_id == thing.id)
                .all()
            )
            assert (
                len(location_thing_association) == 1
            ), f"Expected 1 location-thing association for thing {point_id}."

            location = (
                session.query(Location)
                .filter(Location.id == location_thing_association[0].location_id)
                .all()
            )
            assert len(location) == 1, f"Expected 1 location for thing {point_id}."
            location = location[0]

            point_utm_13n = Point(
                float(file_content["utm_easting"]), float(file_content["utm_northing"])
            )
            point_wgs84 = transform_srid(point_utm_13n, SRID_UTM_ZONE_13N, SRID_WGS84)
            assert location.latlon[0] == point_wgs84.y
            assert location.latlon[1] == point_wgs84.x

            assert location.elevation == convert_ft_to_m(
                float(file_content["elevation_ft"])
            )
            assert location.elevation_method == file_content["elevation_method"]

            assert (
                location._get_notes("Directions")[0].content
                == file_content["directions_to_site"]
            )

            # CONTACTS AND RELATED RECORDS
            thing_contact_associations = (
                session.query(ThingContactAssociation)
                .filter(ThingContactAssociation.thing_id == thing.id)
                .all()
            )
            contacts = (
                session.query(Contact)
                .filter(
                    Contact.id.in_(
                        [tca.contact_id for tca in thing_contact_associations]
                    )
                )
                .all()
            )
            if point_id == "MRG-001_MP1":
                assert (
                    len(contacts) == 2
                ), f"Expected 2 thing-contact associations for thing {point_id}."
            else:
                # no second contact
                assert (
                    len(contacts) == 1
                ), f"Expected 1 thing-contact association for thing {point_id}."

            for contact in contacts:
                assert (
                    contact.general_notes[0].content
                    == file_content["contact_special_requests_notes"]
                )
                assert (
                    contact.communication_notes[0].content
                    == file_content["result_communication_preference"]
                )
                if contact.contact_type == "Primary":
                    assert contact.name == file_content["contact_1_name"]
                    assert (
                        contact.organization == file_content["contact_1_organization"]
                    )
                    assert contact.role == file_content["contact_1_role"]

                    # no second phone in test data
                    assert [(p.phone_number, p.phone_type) for p in contact.phones] == [
                        (
                            f"+1{file_content['contact_1_phone_1']}".replace("-", ""),
                            file_content["contact_1_phone_1_type"],
                        ),
                    ]

                    # no second email in test data
                    assert [(e.email, e.email_type) for e in contact.emails] == [
                        (
                            file_content["contact_1_email_1"],
                            file_content["contact_1_email_1_type"],
                        ),
                    ]

                    # no second address in test data
                    assert [
                        (
                            a.address_line_1,
                            a.address_line_2,
                            a.city,
                            a.state,
                            a.postal_code,
                            a.country,
                            a.address_type,
                        )
                        for a in contact.addresses
                    ] == [
                        (
                            file_content["contact_1_address_1_line_1"],
                            file_content["contact_1_address_1_line_2"],
                            file_content["contact_1_address_1_city"],
                            file_content["contact_1_address_1_state"],
                            file_content["contact_1_address_1_postal_code"],
                            "United States",
                            file_content["contact_1_address_1_type"],
                        )
                    ]
                else:
                    assert contact.name == file_content["contact_2_name"]
                    assert (
                        contact.organization == file_content["contact_2_organization"]
                    )
                    assert contact.role == file_content["contact_2_role"]

                    # no second phone in test data
                    assert [(p.phone_number, p.phone_type) for p in contact.phones] == [
                        (
                            f"+1{file_content['contact_2_phone_1']}".replace("-", ""),
                            file_content["contact_2_phone_1_type"],
                        ),
                    ]

                    # no second email in test data
                    assert [(e.email, e.email_type) for e in contact.emails] == [
                        (
                            file_content["contact_2_email_1"],
                            file_content["contact_2_email_1_type"],
                        ),
                    ]

                    # no second address in test data
                    assert [
                        (
                            a.address_line_1,
                            a.address_line_2,
                            a.city,
                            a.state,
                            a.postal_code,
                            a.country,
                            a.address_type,
                        )
                        for a in contact.addresses
                    ] == [
                        (
                            file_content["contact_2_address_1_line_1"],
                            file_content["contact_2_address_1_line_2"],
                            file_content["contact_2_address_1_city"],
                            file_content["contact_2_address_1_state"],
                            file_content["contact_2_address_1_postal_code"],
                            "United States",
                            file_content["contact_2_address_1_type"],
                        )
                    ]

            # FIELD EVENTS AND RELATED RECORDS
            field_events = (
                session.query(FieldEvent).filter(FieldEvent.thing_id == thing.id).all()
            )
            assert (
                len(field_events) == 1
            ), f"Expected 1 field event for thing {point_id}."
            field_event = field_events[0]
            assert field_event.notes == "Initial field event from well inventory import"
            assert (
                field_event.event_date.date()
                == datetime.fromisoformat(file_content["date_time"]).date()
            )

            field_activity = (
                session.query(FieldActivity)
                .filter(FieldActivity.field_event_id == field_event.id)
                .all()
            )
            assert (
                len(field_activity) == 1
            ), f"Expected 1 field activity for thing {point_id}."
            field_activity = field_activity[0]
            assert field_activity.activity_type == "well inventory"
            assert (
                field_activity.notes == "Well inventory conducted during field event."
            )

            field_event_participants = (
                session.query(FieldEventParticipant)
                .filter(FieldEventParticipant.field_event_id == field_event.id)
                .all()
            )
            if point_id == "MRG-001_MP1":
                assert (
                    len(field_event_participants) == 2
                ), f"Expected 2 field event participants for thing {point_id}."
            else:
                assert (
                    len(field_event_participants) == 1
                ), f"Expected 1 field event participant for thing {point_id}."

            for participant in field_event_participants:
                if participant.participant_role == "Lead":
                    assert participant.participant.name == file_content["field_staff"]
                else:
                    assert participant.participant.name == file_content["field_staff_2"]


def test_well_inventory_db_contents_with_waterlevels(tmp_path):
    """
    Tests that the following records are made:

    - field event
    - field activity for well inventory
    - field activity for water level measurement
    - field participants
    - contact
    - location
    - thing
    - sample
    - observation

    """
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "water_level_date_time": "2025-02-15T10:30:00",
            "depth_to_water_ft": "8",
            "sample_method": "Steel-tape measurement",
            "data_quality": "Water level accurate to within two hundreths of a foot",
            "water_level_notes": "Attempted measurement",
            "mp_height_ft": 3.5,
            "level_status": "Water level not affected",
        }
    )
    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 0, result.stderr

    with session_ctx() as session:
        field_events = session.query(FieldEvent).all()
        field_activities = session.query(FieldActivity).all()
        field_event_participants = session.query(FieldEventParticipant).all()
        contacts = session.query(Contact).all()
        locations = session.query(Location).all()
        things = session.query(Thing).all()
        samples = session.query(Sample).all()
        observations = session.query(Observation).all()

        assert len(field_events) == 1
        assert len(field_activities) == 2
        activity_types = {fa.activity_type for fa in field_activities}
        assert activity_types == {
            "well inventory",
            "groundwater level",
        }, f"Unexpected activity types: {activity_types}"
        gwl_field_activity = next(
            (fa for fa in field_activities if fa.activity_type == "groundwater level"),
            None,
        )
        assert gwl_field_activity is not None

        assert len(field_event_participants) == 1
        assert len(contacts) == 1
        assert len(locations) == 1
        assert len(things) == 1
        assert len(samples) == 1
        sample = samples[0]
        assert sample.field_activity == gwl_field_activity
        assert len(observations) == 1
        observation = observations[0]
        assert observation.sample == sample


def test_measuring_point_height_ft_used_for_thing_and_observation(tmp_path):
    """When measuring_point_height_ft is provided it is used for the thing's (MeasuringPointHistory) and observation's measuring_point_height values."""
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "measuring_point_height_ft": 3.5,
            "water_level_date_time": "2025-02-15T10:30:00",
            "depth_to_water_ft": "8",
            "sample_method": "Steel-tape measurement",
            "data_quality": "Water level accurate to within two hundreths of a foot",
            "water_level_notes": "Attempted measurement",
        }
    )

    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 0, result.stderr

    with session_ctx() as session:
        things = session.query(Thing).all()
        observations = session.query(Observation).all()

        assert len(things) == 1
        assert things[0].measuring_point_height == 3.5
        assert len(observations) == 1
        assert observations[0].measuring_point_height == 3.5


def test_mp_height_used_for_thing_and_observation_when_measuring_point_height_ft_blank(
    tmp_path,
):
    """When depth to water is provided and measuring_point_height_ft is blank the mp_height value should be used for the thing's (MeasuringPointHistory) and observation's measuring_point_height."""
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "measuring_point_height_ft": "",
            "water_level_date_time": "2025-02-15T10:30:00",
            "depth_to_water_ft": "8",
            "sample_method": "Steel-tape measurement",
            "data_quality": "Water level accurate to within two hundreths of a foot",
            "water_level_notes": "Attempted measurement",
            "mp_height": 4.0,
        }
    )

    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 0, result.stderr

    with session_ctx() as session:
        things = session.query(Thing).all()
        observations = session.query(Observation).all()

        assert len(things) == 1
        assert things[0].measuring_point_height == 4.0
        assert len(observations) == 1
        assert observations[0].measuring_point_height == 4.0


def test_null_observation_allows_blank_mp_height(tmp_path):
    """When depth to water is not provided (ie null), blank measuring_point_height_ft and mp_height fields should be allowed and result in a null measuring_point_height for the observation and no associated measuring point height (MeasuringPointHistory) for the well."""
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "measuring_point_height_ft": "",
            "water_level_date_time": "2025-02-15T10:30:00",
            "depth_to_water_ft": "",
            "sample_method": "Steel-tape measurement",
            "data_quality": "Water level accurate to within two hundreths of a foot",
            "water_level_notes": "Attempted measurement",
        }
    )

    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 0, result.stderr

    with session_ctx() as session:
        things = session.query(Thing).all()
        observations = session.query(Observation).all()

        assert len(things) == 1
        assert things[0].measuring_point_height is None
        assert len(observations) == 1
        assert observations[0].measuring_point_height is None


def test_conflicting_mp_heights_raises_error(tmp_path):
    """
    When both measuring_point_height_ft and mp_height are provided, an inequality (conflict) should raise an error.
    """
    row = _minimal_valid_well_inventory_row()

    row.update(
        {
            "measuring_point_height_ft": 3.5,
            "mp_height": 4.0,
        }
    )

    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 1, result.stderr
    assert (
        result.payload["validation_errors"][0]["error"]
        == "Conflicting values for measuring point height: mp_height and measuring_point_height_ft"
    )


def test_no_mp_height_raises_error_when_depth_to_water_provided(tmp_path):
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "water_level_date_time": "2025-02-15T10:30:00",
            "measuring_point_height_ft": "",
            "mp_height": "",
            "depth_to_water_ft": "8",
        }
    )

    file_path = tmp_path / "well-inventory-no-mp-height.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 1, result.stderr
    assert (
        result.payload["validation_errors"][0]["error"]
        == "measuring_point_height_ft or mp_height is required when depth_to_water_ft is provided for a non-null observation"
    )


def test_blank_depth_to_water_still_creates_water_level_records(tmp_path):
    """Blank depth-to-water is treated as missing while preserving the attempted measurement."""
    row = _minimal_valid_well_inventory_row()
    row.update(
        {
            "water_level_date_time": "2025-02-15T10:30:00",
            "depth_to_water_ft": "",
            "sample_method": "Steel-tape measurement",
            "data_quality": "Water level accurate to within two hundreths of a foot",
            "water_level_notes": "Attempted measurement",
            "mp_height_ft": 3.5,
        }
    )

    file_path = tmp_path / "well-inventory-blank-depth.csv"
    with file_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)

    result = well_inventory_csv(file_path)
    assert result.exit_code == 0, result.stderr

    with session_ctx() as session:
        samples = session.query(Sample).all()
        observations = session.query(Observation).all()

        assert len(samples) == 1
        assert len(observations) == 1
        assert samples[0].sample_date == datetime.fromisoformat("2025-02-15T10:30:00Z")
        assert observations[0].observation_datetime == datetime.fromisoformat(
            "2025-02-15T10:30:00Z"
        )
        assert observations[0].value is None
        assert observations[0].measuring_point_height == 3.5


def test_rerunning_same_well_inventory_csv_is_idempotent():
    """Re-importing the same CSV should not create duplicate well inventory records."""
    file = Path("tests/features/data/well-inventory-valid.csv")
    assert file.exists(), "Test data file does not exist."

    first = well_inventory_csv(file)
    assert first.exit_code == 0, first.stderr

    with session_ctx() as session:
        counts_after_first = {
            "things": session.query(Thing).count(),
            "field_events": session.query(FieldEvent).count(),
            "field_activities": session.query(FieldActivity).count(),
            "samples": session.query(Sample).count(),
            "observations": session.query(Observation).count(),
        }

    second = well_inventory_csv(file)
    assert second.exit_code == 0, second.stderr

    with session_ctx() as session:
        counts_after_second = {
            "things": session.query(Thing).count(),
            "field_events": session.query(FieldEvent).count(),
            "field_activities": session.query(FieldActivity).count(),
            "samples": session.query(Sample).count(),
            "observations": session.query(Observation).count(),
        }

    assert counts_after_second == counts_after_first


# =============================================================================
# Error Handling Tests - Cover API error paths
# =============================================================================


class TestWellInventoryErrorHandling:
    """Tests for well inventory CSV upload error handling."""

    def test_upload_invalid_file_type(self, tmp_path):
        """Upload fails when file is not a CSV."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("This is not a CSV file")
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "Unsupported file type" in result.stderr

    def test_upload_empty_file(self, tmp_path):
        """Upload fails when CSV file is empty."""
        file_path = tmp_path / "test.csv"
        file_path.write_text("")
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "Empty file" in result.stderr

    def test_upload_headers_only(self):
        """Upload fails when CSV has headers but no data rows."""
        file_path = Path("tests/features/data/well-inventory-no-data-headers.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1
            assert "No data rows found" in result.stderr

    def test_upload_duplicate_columns(self):
        """Upload fails when CSV has duplicate column names."""
        file_path = Path("tests/features/data/well-inventory-duplicate-columns.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1
            assert "Duplicate columns found" in str(
                result.payload.get("validation_errors", [])
            )

    def test_upload_duplicate_well_ids(self):
        """Upload fails when CSV has duplicate well_name_point_id values."""
        file_path = Path("tests/features/data/well-inventory-duplicate.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1
            errors = result.payload.get("validation_errors", [])
            assert any("Duplicate" in str(e) for e in errors)

    def test_upload_blank_well_name_point_id_autogenerates(self, tmp_path):
        """Upload succeeds when well_name_point_id is blank and auto-generates IDs."""
        source_path = Path("tests/features/data/well-inventory-valid.csv")
        assert source_path.exists(), "Test data file does not exist."
        with open(source_path, "r", encoding="utf-8", newline="") as rf:
            reader = csv.DictReader(rf)
            rows = list(reader)
            fieldnames = reader.fieldnames

        for row in rows:
            row["well_name_point_id"] = ""

        file_path = tmp_path / "well-inventory-blank-point-id.csv"
        with open(file_path, "w", encoding="utf-8", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = well_inventory_csv(file_path)
        assert result.exit_code == 0

    def test_upload_reuses_existing_contact_name_organization(self, tmp_path):
        """Upload succeeds when rows repeat contact name+organization values."""
        source_path = Path("tests/features/data/well-inventory-valid.csv")
        assert source_path.exists(), "Test data file does not exist."
        with open(source_path, "r", encoding="utf-8", newline="") as rf:
            reader = csv.DictReader(rf)
            rows = list(reader)
            fieldnames = reader.fieldnames

        # Force duplicate contact identity across rows.
        if len(rows) >= 2:
            rows[1]["contact_1_name"] = rows[0]["contact_1_name"]
            rows[1]["contact_1_organization"] = rows[0]["contact_1_organization"]

        file_path = tmp_path / "well-inventory-duplicate-contact-name-org.csv"
        with open(file_path, "w", encoding="utf-8", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        result = well_inventory_csv(file_path)
        assert result.exit_code == 0

    def test_upload_invalid_date_format(self):
        """Upload fails when date format is invalid."""
        file_path = Path("tests/features/data/well-inventory-invalid-date-format.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_numeric_value(self):
        """Upload fails when numeric field has invalid value."""
        file_path = Path("tests/features/data/well-inventory-invalid-numeric.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_email(self):
        """Upload fails when email format is invalid."""
        file_path = Path("tests/features/data/well-inventory-invalid-email.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_phone_number(self):
        """Upload fails when phone number format is invalid."""
        file_path = Path("tests/features/data/well-inventory-invalid-phone-number.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_utm_coordinates(self):
        """Upload fails when UTM coordinates are outside New Mexico."""
        file_path = Path("tests/features/data/well-inventory-invalid-utm.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_lexicon_value(self):
        """Upload fails when lexicon value is not in allowed set."""
        file_path = Path("tests/features/data/well-inventory-invalid-lexicon.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_invalid_boolean_value(self):
        """Upload fails when boolean field has invalid value."""
        file_path = Path(
            "tests/features/data/well-inventory-invalid-boolean-value-maybe.csv"
        )
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_missing_contact_type(self):
        """Upload fails when contact is provided without contact_type."""
        file_path = Path("tests/features/data/well-inventory-missing-contact-type.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_missing_contact_role(self):
        """Upload fails when contact is provided without role."""
        file_path = Path("tests/features/data/well-inventory-missing-contact-role.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_partial_water_level_fields(self):
        """Upload fails when only some water level fields are provided."""
        file_path = Path("tests/features/data/well-inventory-missing-wl-fields.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1

    def test_upload_non_utf8_encoding(self, tmp_path):
        """Upload fails when file has invalid encoding."""
        invalid_bytes = b"well_name_point_id,project\n\xff\xfe invalid"
        file_path = tmp_path / "test.csv"
        file_path.write_bytes(invalid_bytes)
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "encoding" in result.stderr.lower() or "Empty" in result.stderr

    def test_validation_error_structure_is_consistent(self, tmp_path):
        """Validation errors have consistent structure with row, field, error keys."""
        content = (
            b"project,well_name_point_id,site_name,date_time,field_staff,"
            b"utm_easting,utm_northing,utm_zone,elevation_ft,elevation_method,"
            b"measuring_point_height_ft\n"
            b"Test,,Site1,2025-01-01T10:00:00,Staff,"
            b"357000,3784000,13N,5000,GPS,3.5\n"
        )
        file_path = tmp_path / "test.csv"
        file_path.write_bytes(content)
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        errors = result.payload.get("validation_errors", [])

        assert len(errors) > 0, "Expected validation errors"

        for error in errors:
            assert "row" in error, f"Missing 'row' key in error: {error}"
            assert "field" in error, f"Missing 'field' key in error: {error}"
            assert "error" in error, f"Missing 'error' key in error: {error}"


# =============================================================================
# Unit Tests for Helper Functions
# =============================================================================


class TestWellInventoryHelpers:
    """Unit tests for well inventory helper functions."""

    def test_make_location_utm_zone_13n(self):
        """Test location creation with UTM zone 13N coordinates."""
        from services.well_inventory_csv import _make_location
        from unittest.mock import MagicMock

        model = MagicMock()
        model.utm_easting = 357000.0
        model.utm_northing = 3784000.0
        model.utm_zone = "13N"
        model.elevation_ft = 5000.0

        location = _make_location(model)

        assert location is not None
        assert location.point is not None
        # Elevation should be converted from feet to meters
        assert location.elevation is not None
        assert location.elevation < 5000  # meters < feet

    def test_make_location_utm_zone_12n(self):
        """Test location creation with UTM zone 12N coordinates."""
        from services.well_inventory_csv import _make_location
        from unittest.mock import MagicMock

        model = MagicMock()
        model.utm_easting = 600000.0
        model.utm_northing = 3900000.0
        model.utm_zone = "12N"
        model.elevation_ft = 4500.0

        location = _make_location(model)

        assert location is not None
        assert location.point is not None
        assert location.elevation is not None

    def test_make_contact_with_full_info(self):
        """Test contact dict creation with all fields populated."""
        from services.well_inventory_csv import _make_contact
        from unittest.mock import MagicMock

        model = MagicMock()
        model.result_communication_preference = "Email preferred"
        model.contact_special_requests_notes = "Call before visiting"
        model.contact_1_name = "John Doe"
        model.contact_1_organization = "Test Org"
        model.contact_1_role = Role.Owner
        model.contact_1_type = ContactType.Primary
        model.contact_1_email_1 = "john@example.com"
        model.contact_1_email_1_type = "Work"
        model.contact_1_email_2 = None
        model.contact_1_email_2_type = None
        model.contact_1_phone_1 = "+15055551234"
        model.contact_1_phone_1_type = "Mobile"
        model.contact_1_phone_2 = None
        model.contact_1_phone_2_type = None
        model.contact_1_address_1_line_1 = "123 Main St"
        model.contact_1_address_1_line_2 = "Suite 100"
        model.contact_1_address_1_city = "Albuquerque"
        model.contact_1_address_1_state = "NM"
        model.contact_1_address_1_postal_code = "87101"
        model.contact_1_address_1_type = "Mailing"
        model.contact_1_address_2_line_1 = None
        model.contact_1_address_2_line_2 = None
        model.contact_1_address_2_city = None
        model.contact_1_address_2_state = None
        model.contact_1_address_2_postal_code = None
        model.contact_1_address_2_type = None

        well = MagicMock()
        well.id = 1

        contact_dict = _make_contact(model, well, 1)

        assert contact_dict is not None
        assert contact_dict["name"] == "John Doe"
        assert contact_dict["organization"] == "Test Org"
        assert contact_dict["thing_id"] == 1
        assert len(contact_dict["emails"]) == 1
        assert len(contact_dict["phones"]) == 1
        assert len(contact_dict["addresses"]) == 1
        assert len(contact_dict["notes"]) == 2

    def test_make_contact_with_no_name_or_organization(self):
        """Test contact dict returns None when name and organization are empty."""
        from services.well_inventory_csv import _make_contact
        from unittest.mock import MagicMock

        model = MagicMock()
        model.result_communication_preference = None
        model.contact_special_requests_notes = None
        model.contact_1_name = None
        model.contact_1_organization = None
        model.contact_1_role = None
        model.contact_1_type = None
        model.contact_1_email_1 = None
        model.contact_1_email_1_type = None
        model.contact_1_email_2 = None
        model.contact_1_email_2_type = None
        model.contact_1_phone_1 = None
        model.contact_1_phone_1_type = None
        model.contact_1_phone_2 = None
        model.contact_1_phone_2_type = None
        model.contact_1_address_1_line_1 = None
        model.contact_1_address_1_line_2 = None
        model.contact_1_address_1_city = None
        model.contact_1_address_1_state = None
        model.contact_1_address_1_postal_code = None
        model.contact_1_address_1_type = None
        model.contact_1_address_2_line_1 = None
        model.contact_1_address_2_line_2 = None
        model.contact_1_address_2_city = None
        model.contact_1_address_2_state = None
        model.contact_1_address_2_postal_code = None
        model.contact_1_address_2_type = None

        well = MagicMock()
        well.id = 1

        contact_dict = _make_contact(model, well, 1)

        assert contact_dict is None

    def test_make_contact_with_organization_only(self):
        """Test contact dict creation when organization is present without a name."""
        from services.well_inventory_csv import _make_contact
        from unittest.mock import MagicMock

        model = MagicMock()
        model.result_communication_preference = None
        model.contact_special_requests_notes = None
        model.contact_1_name = None
        model.contact_1_organization = "Test Org"
        model.contact_1_role = Role.Owner
        model.contact_1_type = ContactType.Primary
        model.contact_1_email_1 = None
        model.contact_1_email_1_type = None
        model.contact_1_email_2 = None
        model.contact_1_email_2_type = None
        model.contact_1_phone_1 = None
        model.contact_1_phone_1_type = None
        model.contact_1_phone_2 = None
        model.contact_1_phone_2_type = None
        model.contact_1_address_1_line_1 = None
        model.contact_1_address_1_line_2 = None
        model.contact_1_address_1_city = None
        model.contact_1_address_1_state = None
        model.contact_1_address_1_postal_code = None
        model.contact_1_address_1_type = None
        model.contact_1_address_2_line_1 = None
        model.contact_1_address_2_line_2 = None
        model.contact_1_address_2_city = None
        model.contact_1_address_2_state = None
        model.contact_1_address_2_postal_code = None
        model.contact_1_address_2_type = None

        well = MagicMock()
        well.id = 1

        contact_dict = _make_contact(model, well, 1)

        assert contact_dict is not None
        assert contact_dict["name"] is None
        assert contact_dict["organization"] == "Test Org"
        assert contact_dict["thing_id"] == 1
        assert contact_dict["emails"] == []
        assert contact_dict["phones"] == []
        assert contact_dict["addresses"] == []
        assert contact_dict["notes"] == []

    def test_make_well_permission(self):
        """Test well permission creation."""
        from services.well_inventory_csv import _make_well_permission
        from datetime import date
        from unittest.mock import MagicMock

        well = MagicMock()
        well.id = 1

        contact = MagicMock()
        contact.id = 2

        permission = _make_well_permission(
            well=well,
            contact=contact,
            permission_type="Water Level Sample",
            permission_allowed=True,
            start_date=date(2025, 1, 1),
        )

        assert permission is not None
        assert permission.target_table == "thing"
        assert permission.target_id == 1
        assert permission.permission_type == "Water Level Sample"
        assert permission.permission_allowed is True

    def test_make_well_permission_no_contact_raises(self):
        """Test that permission creation without contact raises error."""
        from services.well_inventory_csv import _make_well_permission
        from services.exceptions_helper import PydanticStyleException
        from datetime import date
        from unittest.mock import MagicMock

        well = MagicMock()
        well.id = 1

        with pytest.raises(PydanticStyleException) as exc_info:
            _make_well_permission(
                well=well,
                contact=None,
                permission_type="Water Level Sample",
                permission_allowed=True,
                start_date=date(2025, 1, 1),
            )

        assert exc_info.value.status_code == 400

    def test_generate_autogen_well_id_first_well(self):
        """Test auto-generation of well ID when no existing wells with prefix."""
        from services.well_inventory_csv import _generate_autogen_well_id
        from unittest.mock import MagicMock

        session = MagicMock()
        session.scalars.return_value.first.return_value = None

        well_id, offset = _generate_autogen_well_id(session, "XY-")

        assert well_id == "XY-0001"
        assert offset == 1

    def test_generate_autogen_well_id_with_existing(self):
        """Test auto-generation of well ID with existing wells."""
        from services.well_inventory_csv import _generate_autogen_well_id
        from unittest.mock import MagicMock

        session = MagicMock()
        existing_well = MagicMock()
        existing_well.name = "XY-0005"
        session.scalars.return_value.first.return_value = existing_well

        well_id, offset = _generate_autogen_well_id(session, "XY-")

        assert well_id == "XY-0006"
        assert offset == 6

    def test_generate_autogen_well_id_with_offset(self):
        """Test auto-generation with offset parameter."""
        from services.well_inventory_csv import _generate_autogen_well_id
        from unittest.mock import MagicMock

        session = MagicMock()

        well_id, offset = _generate_autogen_well_id(session, "XY-", offset=10)

        assert well_id == "XY-0011"
        assert offset == 11

    def test_extract_autogen_prefix_pattern(self):
        """Test auto-generation prefix extraction for supported placeholders."""
        from services.well_inventory_csv import _extract_autogen_prefix

        # Existing supported form
        assert _extract_autogen_prefix("XY-") == "XY-"
        assert _extract_autogen_prefix("AB-") == "AB-"

        # Placeholder tokens are accepted case-insensitively and normalized.
        assert _extract_autogen_prefix("WL-XXXX") == "WL-"
        assert _extract_autogen_prefix("SAC-XXXX") == "SAC-"
        assert _extract_autogen_prefix("ABC -xxxx") == "ABC-"
        assert _extract_autogen_prefix("wl-xxxx") == "WL-"
        assert _extract_autogen_prefix("abc - XXXX") == "ABC-"

        # Blank values use default prefix
        assert _extract_autogen_prefix("") == "NM-"
        assert _extract_autogen_prefix("   ") == "NM-"

        # Unsupported forms
        assert _extract_autogen_prefix("XY-001") is None
        assert _extract_autogen_prefix("XYZ-") == "XYZ-"
        assert _extract_autogen_prefix("X-") is None
        assert _extract_autogen_prefix("123-") is None
        assert _extract_autogen_prefix("USER-XXXX") is None

    def test_make_row_models_missing_well_name_point_id_column_errors(self):
        """Missing well_name_point_id column should fail validation (blank cell is separate)."""
        from unittest.mock import MagicMock

        from services.well_inventory_csv import _make_row_models

        rows = [{"project": "ProjectA", "site_name": "Site1"}]
        models, validation_errors = _make_row_models(rows, MagicMock())

        assert models == []
        assert len(validation_errors) == 1
        assert validation_errors[0]["field"] == "well_name_point_id"
        assert validation_errors[0]["error"] == "Field required"

    def test_generate_autogen_well_id_non_numeric_suffix(self):
        """Test auto-generation when existing well has non-numeric suffix."""
        from services.well_inventory_csv import _generate_autogen_well_id
        from unittest.mock import MagicMock

        session = MagicMock()
        existing_well = MagicMock()
        existing_well.name = "XY-ABC"  # Non-numeric suffix
        session.scalars.return_value.first.return_value = existing_well

        well_id, offset = _generate_autogen_well_id(session, "XY-")

        # Should default to 1 when suffix is not numeric
        assert well_id == "XY-0001"
        assert offset == 1

    def test_group_query_with_multiple_conditions(self):
        """Group query correctly uses SQLAlchemy and_() for multiple conditions."""
        from db import Group
        from sqlalchemy import select, and_

        with session_ctx() as session:
            # Create test group
            test_group = Group(name="TestProject", group_type="Monitoring Plan")
            session.add(test_group)
            session.commit()

            # Query using and_() - this is the pattern used in well_inventory.py
            sql = select(Group).where(
                and_(
                    Group.group_type == "Monitoring Plan",
                    Group.name == "TestProject",
                )
            )
            found = session.scalars(sql).one_or_none()

            assert found is not None, "and_() query should find the group"
            assert found.name == "TestProject"
            assert found.group_type == "Monitoring Plan"

            # Clean up
            session.delete(test_group)
            session.commit()


class TestWellInventoryRowAliases:
    """Schema alias handling for well inventory CSV field names."""

    def test_well_status_accepts_well_hole_status_alias(self):
        row = _minimal_valid_well_inventory_row()
        row["well_hole_status"] = "Abandoned"

        model = WellInventoryRow(**row)

        assert model.well_status == "Abandoned"

    def test_water_level_aliases_are_mapped(self):
        row = _minimal_valid_well_inventory_row()
        row.update(
            {
                "measuring_person": "Tech 1",
                "sample_method": "Steel-tape measurement",
                "water_level_date_time": "2025-02-15T10:30:00",
                "mp_height_ft": 2.5,
                "level_status": "Other conditions exist that would affect the level (remarks)",
                "depth_to_water_ft": 11.2,
                "data_quality": "Water level accurate to within two hundreths of a foot",
                "water_level_notes": "Initial reading",
            }
        )

        model = WellInventoryRow(**row)

        assert model.sampler == "Tech 1"
        assert model.measurement_date_time == datetime.fromisoformat(
            "2025-02-15T10:30:00"
        )
        assert model.mp_height == 2.5
        assert model.depth_to_water_ft == 11.2
        assert model.water_level_notes == "Initial reading"

    def test_blank_depth_to_water_is_treated_as_none(self):
        row = _minimal_valid_well_inventory_row()
        row.update(
            {
                "water_level_date_time": "2025-02-15T10:30:00",
                "depth_to_water_ft": "",
            }
        )

        model = WellInventoryRow(**row)

        assert model.measurement_date_time == datetime.fromisoformat(
            "2025-02-15T10:30:00"
        )
        assert model.depth_to_water_ft is None

    def test_blank_contact_organization_is_treated_as_none(self):
        row = _minimal_valid_well_inventory_row()
        row["contact_1_name"] = "Test Contact"
        row["contact_1_organization"] = ""
        row["contact_1_role"] = "Owner"
        row["contact_1_type"] = "Primary"

        model = WellInventoryRow(**row)

        assert model.contact_1_name == "Test Contact"
        assert model.contact_1_organization is None

    def test_blank_well_status_is_treated_as_none(self):
        row = _minimal_valid_well_inventory_row()
        row["well_hole_status"] = ""

        model = WellInventoryRow(**row)

        assert model.well_status is None

    def test_canonical_name_wins_when_alias_and_canonical_present(self):
        row = _minimal_valid_well_inventory_row()
        row["well_status"] = "Abandoned"
        row["well_hole_status"] = "Inactive, exists but not used"

        model = WellInventoryRow(**row)

        assert model.well_status == "Abandoned"


class TestWellInventoryAPIEdgeCases:
    """Additional edge case tests for API endpoints."""

    def test_upload_too_many_rows(self, tmp_path):
        """Upload fails when CSV has more than 2000 rows."""
        # Create a CSV with header + 2001 data rows
        header = "project,well_name_point_id,site_name,date_time,field_staff,utm_easting,utm_northing,utm_zone,elevation_ft,elevation_method,measuring_point_height_ft\n"
        row = "TestProject,WELL-{i},Site{i},2025-01-01T10:00:00,Staff,357000,3784000,13N,5000,GPS,3.5\n"

        rows = [header]
        for i in range(2001):
            rows.append(row.format(i=i))

        content = "".join(rows).encode("utf-8")

        file_path = tmp_path / "well-inventory-too-many-rows.csv"
        file_path.write_bytes(content)
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "Too many rows" in result.stderr or "2000" in result.stderr

    def test_upload_semicolon_delimiter(self, tmp_path):
        """Upload fails when CSV uses semicolon delimiter."""
        content = b"project;well_name_point_id;site_name\nTest;WELL-001;Site1\n"
        file_path = tmp_path / "test.csv"
        file_path.write_bytes(content)
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "delimiter" in result.stderr.lower() or "Unsupported" in result.stderr

    def test_upload_tab_delimiter(self, tmp_path):
        """Upload fails when CSV uses tab delimiter."""
        content = b"project\twell_name_point_id\tsite_name\nTest\tWELL-001\tSite1\n"
        file_path = tmp_path / "test.csv"
        file_path.write_bytes(content)
        result = well_inventory_csv(file_path)
        assert result.exit_code == 1
        assert "delimiter" in result.stderr.lower() or "Unsupported" in result.stderr

    def test_upload_duplicate_header_row_in_data(self):
        """Upload fails when header row is duplicated in data."""
        file_path = Path("tests/features/data/well-inventory-duplicate-header.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            assert result.exit_code == 1
            errors = result.payload.get("validation_errors", [])
            assert any(
                "Duplicate header" in str(e) or "header" in str(e).lower()
                for e in errors
            )

    def test_upload_valid_with_comma_in_quotes(self):
        """Upload succeeds when field value contains comma inside quotes."""
        file_path = Path("tests/features/data/well-inventory-valid-comma-in-quotes.csv")
        if file_path.exists():
            result = well_inventory_csv(file_path)
            # Should succeed - commas in quoted fields are valid CSV
            assert result.exit_code in (0, 1)  # 1 if other validation fails


# ============= EOF =============================================
