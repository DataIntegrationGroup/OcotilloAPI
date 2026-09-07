# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
"""The internal-only water well field operations layer (e1f2a3b4c5d6).

What is worth testing here is not that the columns exist but that the layer's
load-bearing rules hold: a well with no measurements still appears, a
permission with no record reads NULL rather than false, a history record
whose window has closed is not treated as current, and a currently-installed
sensor that is not a logger is still visible in the equipment columns even
though it does not count towards has_datalogger.

See docs/water-well-field-operations-layer.md.
"""

from datetime import date, datetime, timedelta
from importlib.util import find_spec

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.dependencies import (
    admin_function,
    amp_admin_function,
    amp_editor_function,
    amp_viewer_function,
    editor_function,
    viewer_function,
)
from db import (
    AquiferSystem,
    Deployment,
    LexiconTerm,
    Notes,
    FieldAccessConsent,
    Sensor,
    StatusHistory,
    Thing,
    ThingAquiferAssociation,
    WellScreen,
)
from db.engine import session_ctx
from tests import override_authentication

pytestmark = pytest.mark.skipif(
    find_spec("pygeoapi") is None,
    reason="pygeoapi is not installed in this environment",
)

VIEW = "ogc_internal_water_well_field_operations"
STATS_VIEW = "ogc_internal_water_well_field_operations_stats"


@pytest.fixture(scope="module")
def today():
    """The database's idea of today, not Python's.

    The view computes its `days_since_*` columns against CURRENT_DATE, which is
    evaluated in the database session's timezone. That is UTC here while the
    developer running the tests may not be, so a date read from Python is off
    by one for part of every day. Read it from the same place the view does.
    """
    with session_ctx() as session:
        return session.execute(text("SELECT CURRENT_DATE")).scalar()


@pytest.fixture(scope="module")
def yesterday(today):
    return today - timedelta(days=1)


@pytest.fixture(scope="module")
def last_year(today):
    return today - timedelta(days=365)


@pytest.fixture(scope="module")
def ogc_client(ogc_app):
    app = ogc_app
    for dependency in (
        admin_function,
        editor_function,
        amp_admin_function,
        amp_editor_function,
    ):
        app.dependency_overrides[dependency] = override_authentication(
            default={"name": "foobar", "sub": "1234567890"}
        )
    for dependency in (viewer_function, amp_viewer_function):
        app.dependency_overrides[dependency] = override_authentication()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = {}


def _row(session, thing_id, columns):
    return session.execute(
        text(f"SELECT {columns} FROM {VIEW} WHERE id = :thing_id"),
        {"thing_id": thing_id},
    ).one()


def _refresh_stats(session):
    session.execute(text(f"REFRESH MATERIALIZED VIEW {STATS_VIEW}"))
    session.commit()


# ------------------------------------------------------------------ row set


def test_a_well_with_no_measurements_still_appears(water_well_thing):
    # water_well_summary drops wells with no readings, because a summary of
    # nothing says nothing. This layer must not: a well nobody has measured is
    # exactly the well a crew needs to find.
    with session_ctx() as session:
        _refresh_stats(session)
        row = _row(
            session,
            water_well_thing.id,
            "name, manual_water_level_count, chemistry_sample_count, "
            "continuous_reading_count, days_since_manual_water_level",
        )

    assert row.name == "Test Well"
    assert row.manual_water_level_count == 0
    assert row.chemistry_sample_count == 0
    assert row.continuous_reading_count == 0
    # No reading means no elapsed time to report, not zero days since one.
    assert row.days_since_manual_water_level is None


def test_latitude_and_longitude_match_the_geometry(water_well_thing):
    with session_ctx() as session:
        row = session.execute(
            text(
                "SELECT latitude, longitude, ST_Y(point) AS geom_y, "
                f"ST_X(point) AS geom_x FROM {VIEW} WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

    # Decimal degrees on WGS 84, read off the same point the geometry carries.
    assert row.latitude == row.geom_y
    assert row.longitude == row.geom_x
    assert -180 <= row.longitude <= 180
    assert -90 <= row.latitude <= 90


# ------------------------------------------------------------- construction


def test_formation_completion_description_reads_the_lexicon_definition(
    water_well_thing,
):
    with session_ctx() as session:
        term = LexiconTerm(
            term="Test Formation XYZ",
            definition="A test formation used only by this test",
        )
        session.add(term)
        session.commit()

        thing = session.get(Thing, water_well_thing.id)
        thing.formation_completion_code = term.term
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "formation_completion_code, formation_completion_description",
        )
        assert row.formation_completion_code == "Test Formation XYZ"
        assert (
            row.formation_completion_description
            == "A test formation used only by this test"
        )

        thing.formation_completion_code = None
        session.commit()
        session.delete(term)
        session.commit()


def test_formation_completion_description_is_null_without_a_code(water_well_thing):
    with session_ctx() as session:
        row = _row(session, water_well_thing.id, "formation_completion_description")

    assert row.formation_completion_description is None


def test_aquifer_system_name_is_comma_joined(water_well_thing):
    with session_ctx() as session:
        system_a = AquiferSystem(
            name="Test Aquifer A", primary_aquifer_type="Unconfined multiple aquifers"
        )
        system_b = AquiferSystem(
            name="Test Aquifer B", primary_aquifer_type="Confined multiple aquifers"
        )
        session.add_all([system_a, system_b])
        session.commit()

        associations = [
            ThingAquiferAssociation(
                thing_id=water_well_thing.id, aquifer_system_id=system_a.id
            ),
            ThingAquiferAssociation(
                thing_id=water_well_thing.id, aquifer_system_id=system_b.id
            ),
        ]
        session.add_all(associations)
        session.commit()

        row = _row(session, water_well_thing.id, "aquifer_system_name")
        assert row.aquifer_system_name == "Test Aquifer A, Test Aquifer B"

        for association in associations:
            session.delete(association)
        session.delete(system_a)
        session.delete(system_b)
        session.commit()


def test_screens_list_every_interval_position_aligned(
    water_well_thing, well_screen, second_well_screen
):
    with session_ctx() as session:
        row = _row(
            session,
            water_well_thing.id,
            "screen_count, screen_depth_top, screen_depth_bottom, "
            "screen_description",
        )

    # well_screen is 10-20ft, second_well_screen is 30-40ft, so
    # screen_depth_top's ascending order puts well_screen first throughout.
    assert row.screen_count == 2
    assert row.screen_depth_top == "10; 30"
    assert row.screen_depth_bottom == "20; 40"
    assert row.screen_description == (
        "Test well screen description; Test well screen description"
    )


def test_a_null_screen_field_leaves_an_empty_slot_not_a_dropped_position(
    water_well_thing, well_screen
):
    # A screen with no recorded bottom depth or description. Plain
    # string_agg would drop those NULLs, shortening screen_depth_bottom and
    # screen_description to one entry each while screen_depth_top still had
    # two -- position 0 would then read as well_screen's bottom depth when
    # it is actually the incomplete screen's.
    with session_ctx() as session:
        incomplete_screen = WellScreen(
            thing_id=water_well_thing.id,
            screen_depth_top=5.0,
            screen_depth_bottom=None,
            screen_description=None,
            release_status="draft",
        )
        session.add(incomplete_screen)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "screen_depth_top, screen_depth_bottom, screen_description",
        )

        # 5.0 sorts before well_screen's 10.0, so position 0 is the
        # incomplete screen throughout -- an empty segment where its values
        # are null, not a shorter list.
        assert row.screen_depth_top == "5; 10"
        assert row.screen_depth_bottom == "; 20"
        assert row.screen_description == "; Test well screen description"

        session.delete(incomplete_screen)
        session.commit()


# --------------------------------------------------------------- permissions


def test_permission_with_no_record_is_null_not_false(water_well_thing):
    with session_ctx() as session:
        row = _row(
            session,
            water_well_thing.id,
            "may_measure_water_level, may_sample_water_chemistry, "
            "may_install_datalogger",
        )

    # NULL means nobody has asked the landowner. Rendering it as "no" would
    # tell a crew the well is off limits when the truth is unknown.
    assert row.may_measure_water_level is None
    assert row.may_sample_water_chemistry is None
    assert row.may_install_datalogger is None


def test_permission_distinguishes_granted_from_refused(
    water_well_thing, contact, last_year
):
    with session_ctx() as session:
        granted = FieldAccessConsent(
            contact_id=contact.id,
            target_id=water_well_thing.id,
            target_table="thing",
            permission_type="Water Level Sample",
            permission_allowed=True,
            start_date=last_year,
        )
        refused = FieldAccessConsent(
            contact_id=contact.id,
            target_id=water_well_thing.id,
            target_table="thing",
            permission_type="Datalogger Installation",
            permission_allowed=False,
            start_date=last_year,
        )
        session.add_all([granted, refused])
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "may_measure_water_level, may_install_datalogger, "
            "may_sample_water_chemistry, permission_granted_by",
        )

        assert row.may_measure_water_level is True
        assert row.may_install_datalogger is False
        # Untouched permission type stays unknown rather than inheriting either.
        assert row.may_sample_water_chemistry is None
        assert row.permission_granted_by == contact.name

        session.delete(granted)
        session.delete(refused)
        session.commit()


def test_expired_permission_is_not_current(
    water_well_thing, contact, last_year, yesterday
):
    with session_ctx() as session:
        expired = FieldAccessConsent(
            contact_id=contact.id,
            target_id=water_well_thing.id,
            target_table="thing",
            permission_type="Water Level Sample",
            permission_allowed=True,
            start_date=last_year,
            end_date=yesterday,
        )
        session.add(expired)
        session.commit()

        row = _row(session, water_well_thing.id, "may_measure_water_level")
        # A permission that ran out yesterday is not a permission today. This
        # is the divergence from ogc_actively_monitored_wells, which ignores
        # end_date entirely.
        assert row.may_measure_water_level is None

        session.delete(expired)
        session.commit()


# -------------------------------------------------------------------- status


def test_status_reads_the_current_record_not_the_latest(
    water_well_thing, last_year, yesterday
):
    with session_ctx() as session:
        closed = StatusHistory(
            target_id=water_well_thing.id,
            target_table="thing",
            status_type="Monitoring Status",
            status_value="Currently monitored",
            start_date=last_year,
            end_date=yesterday,
            reason="programme ended",
        )
        open_status = StatusHistory(
            target_id=water_well_thing.id,
            target_table="thing",
            status_type="Well Status",
            status_value="Active, pumping well",
            start_date=last_year,
        )
        session.add_all([closed, open_status])
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "monitoring_status, well_status",
        )

        assert row.monitoring_status is None
        assert row.well_status == "Active, pumping well"

        session.delete(closed)
        session.delete(open_status)
        session.commit()


def test_status_types_do_not_bleed_into_each_other(water_well_thing, last_year):
    with session_ctx() as session:
        monitoring = StatusHistory(
            target_id=water_well_thing.id,
            target_table="thing",
            status_type="Monitoring Status",
            status_value="Not currently monitored",
            start_date=last_year,
            reason="landowner asked us to stop",
        )
        session.add(monitoring)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "monitoring_status, well_status, "
            "open_status, datalogger_suitability_status",
        )

        assert row.monitoring_status == "Not currently monitored"
        assert row.well_status is None
        assert row.open_status is None
        assert row.datalogger_suitability_status is None

        session.delete(monitoring)
        session.commit()


# ---------------------------------------------------------------- datalogger


def test_has_datalogger_counts_only_logger_equipment(
    water_well_thing, sensor_to_water_well_thing_deployment
):
    with session_ctx() as session:
        row = _row(
            session,
            water_well_thing.id,
            "has_datalogger, datalogger_deployment_count, "
            "sensor_type, serial_no, recording_interval",
        )

        assert row.has_datalogger is True
        assert row.datalogger_deployment_count == 1
        # Single current sensor: aggregation degenerates to a bare value, no
        # delimiter.
        assert row.sensor_type == "Pressure Transducer"
        assert row.serial_no == "123456"
        assert row.recording_interval == "24"


def test_non_logger_equipment_does_not_make_a_well_instrumented(
    water_well_thing, last_year
):
    with session_ctx() as session:
        barometer = Sensor(
            name="Test Barometer",
            sensor_type="Barometer",
            sensor_status="In Service",
            release_status="draft",
        )
        session.add(barometer)
        session.commit()
        deployment = Deployment(
            sensor_id=barometer.id,
            thing_id=water_well_thing.id,
            installation_date=last_year,
            removal_date=None,
        )
        session.add(deployment)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "has_datalogger, datalogger_deployment_count, sensor_type",
        )
        # A barometer at the well is equipment, not a logger in the well --
        # but it must still be visible as installed equipment, unlike the
        # old logger-only columns this replaces.
        assert row.has_datalogger is False
        assert row.datalogger_deployment_count == 0
        assert row.sensor_type == "Barometer"

        session.delete(deployment)
        session.delete(barometer)
        session.commit()


def test_installed_equipment_lists_every_sensor_position_aligned(
    water_well_thing, sensor, sensor_to_water_well_thing_deployment, last_year
):
    with session_ctx() as session:
        barometer = Sensor(
            name="Test Barometer",
            sensor_type="Barometer",
            model="BaroTroll",
            serial_no="BT-002",
            sensor_status="In Service",
            release_status="draft",
        )
        session.add(barometer)
        session.commit()
        barometer_deployment = Deployment(
            sensor_id=barometer.id,
            thing_id=water_well_thing.id,
            installation_date=last_year,
            removal_date=None,
            recording_interval=60,
            recording_interval_units="minute",
            hanging_point_description="Strapped to fence post",
        )
        session.add(barometer_deployment)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "sensor_type, model, serial_no, recording_interval, "
            "recording_interval_units, hanging_point_desc, has_datalogger, "
            "datalogger_deployment_count",
        )

        # Ordered alphabetically by sensor_type ("Barometer" <
        # "Pressure Transducer"), and every column ordered the same way, so
        # position 0 in each list describes the barometer and position 1 the
        # transducer.
        assert row.sensor_type == "Barometer; Pressure Transducer"
        assert row.model == "BaroTroll; Model X"
        assert row.serial_no == "BT-002; 123456"
        assert row.recording_interval == "60; 24"
        assert row.recording_interval_units == "minute; hour"
        assert row.hanging_point_desc == "Strapped to fence post; hang 10"
        # The non-logger sensor does not count towards the logger-only signal.
        assert row.has_datalogger is True
        assert row.datalogger_deployment_count == 1

        session.delete(barometer_deployment)
        session.delete(barometer)
        session.commit()


def test_a_null_field_on_one_sensor_leaves_an_empty_slot_not_a_dropped_position(
    water_well_thing, sensor, sensor_to_water_well_thing_deployment, last_year
):
    # A camera has no recording interval. Plain string_agg would silently
    # drop that NULL, shortening recording_interval's list to one entry while
    # sensor_type still has two -- position 0 would then read as the
    # camera's interval when it is actually the transducer's. The view
    # COALESCEs to '' specifically so this doesn't happen.
    with session_ctx() as session:
        camera = Sensor(
            name="Test Camera",
            sensor_type="Camera",
            model="Reconyx HC600",
            serial_no=None,
            sensor_status="In Service",
            release_status="draft",
        )
        session.add(camera)
        session.commit()
        camera_deployment = Deployment(
            sensor_id=camera.id,
            thing_id=water_well_thing.id,
            installation_date=last_year,
            removal_date=None,
            recording_interval=None,
            recording_interval_units=None,
            hanging_point_description=None,
        )
        session.add(camera_deployment)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "sensor_type, model, serial_no, recording_interval, "
            "recording_interval_units, hanging_point_desc",
        )

        # "Camera" sorts before "Pressure Transducer", so position 0 is the
        # camera throughout -- an empty segment where its value is null, not
        # a shorter list.
        assert row.sensor_type == "Camera; Pressure Transducer"
        assert row.model == "Reconyx HC600; Model X"
        assert row.serial_no == "; 123456"
        assert row.recording_interval == "; 24"
        assert row.recording_interval_units == "; hour"
        assert row.hanging_point_desc == "; hang 10"

        session.delete(camera_deployment)
        session.delete(camera)
        session.commit()


def test_a_removed_logger_leaves_the_well_uninstrumented(
    water_well_thing, sensor, sensor_to_water_well_thing_deployment, yesterday
):
    with session_ctx() as session:
        deployment = session.get(Deployment, sensor_to_water_well_thing_deployment.id)
        deployment.removal_date = yesterday
        session.commit()

        row = _row(session, water_well_thing.id, "has_datalogger")
        assert row.has_datalogger is False

        deployment.removal_date = None
        session.commit()


# ------------------------------------------------------------- measurements


def test_last_depth_to_water_uses_the_measuring_point_convention(
    water_well_thing, groundwater_level_sample, today
):
    from db import Observation
    from tests import get_parameter_id

    with session_ctx() as session:
        readings = []
        for day, value, measuring_point_height in ((1, 6.0, 1.0), (2, 9.0, 2.0)):
            observation = Observation(
                observation_datetime=datetime(2025, 1, day, 12, 0, 0),
                sample_id=groundwater_level_sample.id,
                parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
                release_status="public",
                value=value,
                unit="ft",
                measuring_point_height=measuring_point_height,
                groundwater_level_reason="Water level not affected",
            )
            session.add(observation)
            readings.append(observation)
        session.commit()
        _refresh_stats(session)

        row = _row(
            session,
            water_well_thing.id,
            "manual_water_level_count, manual_water_level_first_date, "
            "manual_water_level_last_date, last_depth_to_water_ft, "
            "days_since_manual_water_level",
        )

        assert row.manual_water_level_count == 2
        assert row.manual_water_level_first_date == date(2025, 1, 1)
        assert row.manual_water_level_last_date == date(2025, 1, 2)
        # Latest reading is 9 ft from a measuring point 2 ft above ground.
        assert abs(float(row.last_depth_to_water_ft) - 7.0) < 1e-9
        # Computed against today, not against the last refresh.
        assert row.days_since_manual_water_level == (today - date(2025, 1, 2)).days

        for observation in readings:
            session.delete(observation)
        session.commit()
        _refresh_stats(session)


def test_private_readings_are_counted_on_this_internal_layer(
    water_well_thing, groundwater_level_sample
):
    from db import Observation
    from tests import get_parameter_id

    with session_ctx() as session:
        observation = Observation(
            observation_datetime=datetime(2025, 2, 1, 12, 0, 0),
            sample_id=groundwater_level_sample.id,
            parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
            release_status="private",
            value=4.0,
            unit="ft",
            measuring_point_height=1.0,
            groundwater_level_reason="Water level not affected",
        )
        session.add(observation)
        session.commit()
        _refresh_stats(session)

        row = _row(session, water_well_thing.id, "manual_water_level_count")
        # The internal mount is unfiltered by design; this layer has no public
        # twin to keep in step with.
        assert row.manual_water_level_count == 1

        session.delete(observation)
        session.commit()
        _refresh_stats(session)


# ------------------------------------------------------ multi-valued columns


def test_multi_valued_columns_are_comma_joined_text(
    water_well_thing, domestic_well_purpose, irrigation_well_purpose
):
    with session_ctx() as session:
        row = _row(session, water_well_thing.id, "well_purpose")

    # Text, not an array: this layer is exported to File Geodatabase and
    # GeoPackage for offline field use, and neither format has a list type.
    assert isinstance(row.well_purpose, str)
    assert row.well_purpose == "Domestic, Irrigation"


def test_note_types_do_not_bleed_into_each_other(water_well_thing):
    with session_ctx() as session:
        water_note = Notes(
            target_id=water_well_thing.id,
            target_table="thing",
            note_type="Water",
            content="Well produces slightly sulfurous water",
        )
        maintenance_note = Notes(
            target_id=water_well_thing.id,
            target_table="thing",
            note_type="Maintenance",
            content="Pump replaced 2024",
        )
        session.add_all([water_note, maintenance_note])
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "water_notes, maintenance_notes, coordinate_notes, " "owner_comment_notes",
        )

        assert row.water_notes == "Well produces slightly sulfurous water"
        assert row.maintenance_notes == "Pump replaced 2024"
        # Untouched note types stay null rather than inheriting either note.
        assert row.coordinate_notes is None
        assert row.owner_comment_notes is None

        session.delete(water_note)
        session.delete(maintenance_note)
        session.commit()


def test_contacts_and_access_notes_are_published(water_well_thing, contact, phone):
    with session_ctx() as session:
        note = Notes(
            target_id=water_well_thing.id,
            target_table="thing",
            note_type="Access",
            content="Gate is locked, call ahead",
        )
        session.add(note)
        session.commit()

        row = _row(
            session,
            water_well_thing.id,
            "contact_count, primary_contact_name, primary_contact_type, "
            "primary_contact_role, primary_contact_phone, access_notes",
        )

        assert row.contact_count == 1
        assert row.primary_contact_name == contact.name
        assert row.primary_contact_type == "Primary"
        assert row.primary_contact_role == "Owner"
        assert row.primary_contact_phone == phone.phone_number
        assert row.access_notes == "Gate is locked, call ahead"

        session.delete(note)
        session.commit()


# ------------------------------------------------------------------- mounts


def test_layer_is_served_on_the_internal_mount_only(ogc_client):
    internal = ogc_client.get(
        "/ogcapi-internal/collections/water_well_field_operations/items?limit=1"
    )
    assert internal.status_code == 200
    assert internal.json()["type"] == "FeatureCollection"

    public = ogc_client.get(
        "/ogcapi/collections/water_well_field_operations/items?limit=1"
    )
    # The layer publishes landowner contact details; it must not exist at all
    # on the anonymous mount.
    assert public.status_code == 404


def test_every_column_is_documented_on_the_internal_mount(ogc_client):
    response = ogc_client.get(
        "/ogcapi-internal/collections/water_well_field_operations/schema"
    )
    assert response.status_code == 200

    properties = response.json()["properties"]
    gaps = [
        name
        for name, prop in properties.items()
        if name != "geometry" and not prop.get("description")
    ]
    assert not gaps, f"columns with no YAML entry: {gaps}"


def test_permission_columns_explain_their_null_meaning(ogc_client):
    response = ogc_client.get(
        "/ogcapi-internal/collections/water_well_field_operations/schema"
    )
    properties = response.json()["properties"]

    # The three-valued meaning only reaches a consumer through this prose.
    for column in (
        "may_measure_water_level",
        "may_sample_water_chemistry",
        "may_install_datalogger",
    ):
        assert "null" in properties[column]["description"].lower()
