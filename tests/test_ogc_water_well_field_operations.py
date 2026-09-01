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
three load-bearing rules hold: a well with no measurements still appears, a
permission with no record reads NULL rather than false, and a history record
whose window has closed is not treated as current.

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
from core.factory import create_api_app
from db import (
    DataProvenance,
    Deployment,
    Notes,
    PermissionHistory,
    Sensor,
    StatusHistory,
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
def ogc_client():
    app = create_api_app()
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


def test_elevation_method_reads_the_location_provenance(water_well_thing, location):
    with session_ctx() as session:
        row = _row(session, water_well_thing.id, "elevation_method")
        # No provenance record is "not recorded", not a method of "unknown".
        assert row.elevation_method is None

        provenance = DataProvenance(
            target_id=location.id,
            target_table="location",
            field_name="elevation",
            collection_method="Survey-grade GPS",
        )
        session.add(provenance)
        session.commit()

        row = _row(session, water_well_thing.id, "elevation_method")
        assert row.elevation_method == "Survey-grade GPS"

        session.delete(provenance)
        session.commit()


def test_elevation_method_ignores_provenance_for_other_fields(
    water_well_thing, location
):
    with session_ctx() as session:
        provenance = DataProvenance(
            target_id=location.id,
            target_table="location",
            field_name="point",
            collection_method="Survey-grade GPS",
        )
        session.add(provenance)
        session.commit()

        row = _row(session, water_well_thing.id, "elevation_method")
        # How the coordinates were obtained says nothing about the elevation.
        assert row.elevation_method is None

        session.delete(provenance)
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
        granted = PermissionHistory(
            contact_id=contact.id,
            target_id=water_well_thing.id,
            target_table="thing",
            permission_type="Water Level Sample",
            permission_allowed=True,
            start_date=last_year,
        )
        refused = PermissionHistory(
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
        expired = PermissionHistory(
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
            "monitoring_status, monitoring_status_since, well_status, "
            "well_status_since",
        )

        assert row.monitoring_status is None
        assert row.monitoring_status_since is None
        assert row.well_status == "Active, pumping well"
        assert row.well_status_since == last_year

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
            "monitoring_status, monitoring_status_reason, well_status, "
            "open_status, access_status, datalogger_suitability_status",
        )

        assert row.monitoring_status == "Not currently monitored"
        assert row.monitoring_status_reason == "landowner asked us to stop"
        assert row.well_status is None
        assert row.open_status is None
        assert row.access_status is None
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
            "datalogger_sensor_type, datalogger_serial_no, "
            "datalogger_recording_interval",
        )

        assert row.has_datalogger is True
        assert row.datalogger_deployment_count == 1
        assert row.datalogger_sensor_type == "Pressure Transducer"
        assert row.datalogger_serial_no == "123456"
        assert row.datalogger_recording_interval == 24


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
            "has_datalogger, datalogger_deployment_count",
        )
        # A barometer at the well is equipment, not a logger in the well.
        assert row.has_datalogger is False
        assert row.datalogger_deployment_count == 0

        session.delete(deployment)
        session.delete(barometer)
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
        row = _row(session, water_well_thing.id, "well_purposes")

    # Text, not an array: this layer is exported to File Geodatabase and
    # GeoPackage for offline field use, and neither format has a list type.
    assert isinstance(row.well_purposes, str)
    assert row.well_purposes == "Domestic, Irrigation"


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
