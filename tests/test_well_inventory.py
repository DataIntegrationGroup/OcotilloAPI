"""
The feature tests for the well inventory csv upload tests if the API can
successfully process a well inventory upload and create the appropriate
response, but it does not verify that the database contents are correct.

This module contains tests that verify the correctness of the database
contents after a well inventory upload.
"""

import csv
from datetime import datetime
from pathlib import Path
import pytest
from shapely import Point

from core.constants import SRID_UTM_ZONE_13N, SRID_WGS84
from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)
from db import (
    Location,
    LocationThingAssociation,
    Thing,
    Contact,
    ThingContactAssociation,
    FieldEvent,
    FieldActivity,
    FieldEventParticipant,
)
from db.engine import session_ctx
from main import app
from services.util import transform_srid, convert_ft_to_m
from tests import client, override_authentication


@pytest.fixture(scope="module", autouse=True)
def override_authentication_dependency_fixture():
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[viewer_function] = override_authentication()
    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()

    yield

    app.dependency_overrides = {}


def test_well_inventory_db_contents():
    """
    Test that the well inventory upload creates the correct database contents.

    This test verifies that the well inventory upload creates the correct
    database contents by checking for the presence of specific records in
    the database.
    """

    file = Path("tests/features/data/well-inventory-valid.csv")
    assert file.exists(), "Test data file does not exist."

    # read file into dictionary to compare values with DB objects
    with open(file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        file_dict = {}

        for row in reader:
            file_dict[row["well_name_point_id"]] = row

    response = client.post(
        "/well-inventory-csv",
        files={"file": open(file, "rb")},
    )
    data = response.json()
    print(data)
    assert (
        response.status_code == 201
    ), f"Unexpected status code: {response.status_code}"

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
                if contact.contact_type == "Primary":
                    assert contact.name == file_content["contact_1_name"]
                    assert (
                        contact.organization == file_content["contact_1_organization"]
                    )
                    assert contact.role == file_content["contact_1_role"]

                    # no second phone in test data
                    assert [(p.phone_number, p.phone_type) for p in contact.phones] == [
                        (
                            f"+1{file_content["contact_1_phone_1"]}".replace("-", ""),
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
                            f"+1{file_content["contact_2_phone_1"]}".replace("-", ""),
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

        # CLEAN UP THE DATABASE AFTER TESTING
        session.query(Thing).delete()
        session.query(ThingContactAssociation).delete()
        session.query(Contact).delete()
        session.query(LocationThingAssociation).delete()
        session.query(Location).delete()
        session.query(FieldEventParticipant).delete()
        session.query(FieldActivity).delete()
        session.query(FieldEvent).delete()
        session.commit()
