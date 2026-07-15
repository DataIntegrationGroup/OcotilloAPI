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
"""Step definitions for A1 (public release_status filter on ogc_* views).

Only the @A1-tagged scenarios in ogc-cleanup-sprint1.feature are implemented
here. The other ~10 tickets sharing that feature file have no steps yet and
stay undefined/dormant, per this ticket's plan.
"""

import importlib
from datetime import date

from alembic import command
from behave import given, when, then
from sqlalchemy import text

from core.dependencies import (
    viewer_function,
    amp_viewer_function,
    amp_editor_function,
    admin_function,
    amp_admin_function,
)
from starlette.testclient import TestClient

from db import (
    Location,
    Thing,
    LocationThingAssociation,
    Group,
    GroupThingAssociation,
    StatusHistory,
    Contact,
    FieldEvent,
    FieldEventParticipant,
    FieldActivity,
    Sample,
    Observation,
    Sensor,
    NMA_Chemistry_SampleInfo,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
)
from db.engine import session_ctx
from tests import get_parameter_id
from tests.features.environment import _alembic_config

# Revision immediately before this ticket's schema migration -- re-verify
# with `alembic heads`/`alembic history` if this file is revisited later,
# since new migrations may have landed since.
PRE_A1_REVISION = "y3z4a5b6c7d8"

# Maps every OGC layer-id used in this feature file's data tables to the
# seed group whose known public/private/draft ids should appear or not
# appear in that layer. The 9 derived/summary layers and
# actively_monitored_wells all key off the same seeded water wells.
LAYER_ID_TO_SEED_KEY = {
    "water_wells": "water_wells",
    "springs": "springs",
    "perennial_streams": "perennial_streams",
    "meteorological_stations": "meteorological_stations",
    "diversions_surface_water": "diversions_surface_water",
    "lakes_ponds_reservoirs": "lakes_ponds_reservoirs",
    "other_things": "other_things",
    "water_well_summary": "water_wells",
    "depth_to_water_trend_wells": "water_wells",
    "water_elevation_wells": "water_wells",
    "major_chemistry_results": "water_wells",
    "minor_chemistry_wells": "water_wells",
    "latest_tds_wells": "water_wells",
    "actively_monitored_wells": "water_wells",
    "avg_tds_wells": "water_wells",
    "latest_depth_to_water_wells": "water_wells",
    "locations": "locations",
    "project_areas": "project_areas",
    "ephemeral_streams": "ephemeral_streams",
    "rock_sample_locations": "rock_sample_locations",
    "soil_gas_sample_locations": "soil_gas_sample_locations",
    "outfalls_wastewater_return_flow": "outfalls_wastewater_return_flow",
}

# Same mapping, keyed by the underlying ogc_* relation name, for the
# SQL-level scenarios (migration-application, downgrade-reversibility).
VIEW_TO_SEED_KEY = {
    f"ogc_{layer_id}": seed_key for layer_id, seed_key in LAYER_ID_TO_SEED_KEY.items()
}

# ogc_locations does not exist before A1 (core/pygeoapi-config.yml pointed
# directly at the raw location table), so downgrade drops it rather than
# recreating an unfiltered copy -- there is no "count before the migration"
# to compare it against once downgraded.
NOT_PRESENT_BEFORE_A1 = {"ogc_locations"}

# Thing-type layers backed by the shared _create_thing_view template --
# a simple Location + Thing pair is enough to exercise these.
SIMPLE_THING_TYPE_LAYERS = [
    ("springs", "spring"),
    ("perennial_streams", "perennial stream"),
    ("meteorological_stations", "meteorological station"),
    ("diversions_surface_water", "diversion of surface water, etc."),
    ("lakes_ponds_reservoirs", "lake, pond or reservoir"),
    ("other_things", "other"),
    ("ephemeral_streams", "ephemeral stream"),
    ("rock_sample_locations", "rock sample location"),
    ("soil_gas_sample_locations", "soil gas sample location"),
    ("outfalls_wastewater_return_flow", "outfall of wastewater or return flow"),
]

# The feature file's "4 already-consistent layers" scenario: today's live
# data for these thing types happens to be 100% public already.
ALREADY_CONSISTENT_LAYER_IDS = {
    "ephemeral_streams",
    "rock_sample_locations",
    "soil_gas_sample_locations",
    "outfalls_wastewater_return_flow",
}

STATUSES = ("public", "private", "draft")


@given("the Ocotillo API is running")
def step_given_ocotillo_api_is_running(context):
    from main import app

    def override_authentication(default=True):
        def closure():
            return default

        return closure

    app.dependency_overrides[amp_admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[admin_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_editor_function] = override_authentication(
        default={"name": "foobar", "sub": "1234567890"}
    )
    app.dependency_overrides[amp_viewer_function] = override_authentication()
    app.dependency_overrides[viewer_function] = override_authentication()

    context.client = TestClient(app)
    assert context.client is not None, "TestClient failed to initialize"


def _seed_thing_with_location(session, thing_type, release_status, name):
    location = Location(
        point="POINT(-106.5 34.0)",
        elevation=1500.0,
        release_status="public",
    )
    session.add(location)
    session.commit()

    thing = Thing(
        name=name,
        first_visit_date="2023-01-01",
        thing_type=thing_type,
        release_status=release_status,
    )
    session.add(thing)
    session.commit()

    assoc = LocationThingAssociation(location=location, thing=thing)
    assoc.effective_start = "2023-01-01T00:00:00Z"
    session.add(assoc)
    session.commit()
    session.refresh(thing)
    return thing


def _seed_water_well(session, release_status, name, monitoring_group):
    well = _seed_thing_with_location(session, "water well", release_status, name)
    # well.id is used to keep every unique-constrained field below distinct
    # across repeated _seed_all() calls within the same behave run (this
    # helper runs once per A1 scenario, sharing one database).
    uid = well.id

    # Observation chain feeding ogc_latest_depth_to_water_wells,
    # ogc_depth_to_water_trend_wells, ogc_water_well_summary,
    # ogc_water_elevation_wells.
    contact = Contact(
        name=f"A1 Contact {uid}",
        role="Owner",
        contact_type="Primary",
        organization="NMBGMR",
        release_status="draft",
    )
    session.add(contact)
    session.commit()

    field_event = FieldEvent(
        thing_id=well.id,
        event_date="2025-01-01T00:00:00Z",
        notes="A1 behave seed field event",
        release_status="draft",
    )
    session.add(field_event)
    session.commit()

    participant = FieldEventParticipant(
        field_event_id=field_event.id,
        contact_id=contact.id,
        participant_role="Lead",
    )
    session.add(participant)
    session.commit()

    field_activity = FieldActivity(
        field_event_id=field_event.id,
        activity_type="groundwater level",
        notes="A1 behave seed field activity",
        release_status="draft",
    )
    session.add(field_activity)
    session.commit()

    sample = Sample(
        field_activity_id=field_activity.id,
        field_event_participant_id=participant.id,
        sample_date="2025-01-01T12:00:00Z",
        sample_name=f"A1 sample {uid}",
        sample_matrix="water",
        sample_method="Steel-tape measurement",
        qc_type="Normal",
        depth_top=None,
        depth_bottom=None,
        notes="A1 behave seed sample",
        release_status="draft",
    )
    session.add(sample)
    session.commit()

    sensor = Sensor(
        name=f"A1 Sensor {uid}",
        sensor_type="Pressure Transducer",
        model="Model X",
        serial_no=f"A1-SN-{uid}",
        pcn_number=f"A1-PCN-{uid}",
        owner_agency="NMBGMR",
        sensor_status="In Service",
        notes="A1 behave seed sensor",
        release_status="draft",
    )
    session.add(sensor)
    session.commit()

    observation = Observation(
        observation_datetime="2025-01-01T00:04:00Z",
        sample_id=sample.id,
        sensor_id=sensor.id,
        parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
        release_status="draft",
        value=10.0,
        unit="ft",
        measuring_point_height=5.0,
        groundwater_level_reason="Water level not affected",
    )
    session.add(observation)
    session.commit()

    # Chemistry rows feeding ogc_avg_tds_wells, ogc_latest_tds_wells,
    # ogc_major_chemistry_results, ogc_minor_chemistry_wells.
    # nma_sample_point_id is varchar(10) -- keep it short.
    sample_point_id = f"A1{uid}"[:10]
    csi = NMA_Chemistry_SampleInfo(
        thing_id=well.id,
        nma_sample_point_id=sample_point_id,
        collection_date="2025-01-02T10:00:00Z",
    )
    session.add(csi)
    session.flush()

    major = NMA_MajorChemistry(
        chemistry_sample_info_id=csi.id,
        analyte="Total Dissolved Solids",
        symbol="TDS",
        sample_value=500.0,
        units="mg/L",
        analysis_date=None,
    )
    session.add(major)

    minor = NMA_MinorTraceChemistry(
        chemistry_sample_info_id=csi.id,
        nma_sample_point_id=sample_point_id,
        analyte="F",
        symbol="",
        sample_value=1.0,
        units="mg/L",
        analysis_date=date(2025, 1, 2),
    )
    session.add(minor)
    session.commit()

    # Water Level Network membership feeding ogc_actively_monitored_wells.
    group_assoc = GroupThingAssociation(group_id=monitoring_group.id, thing_id=well.id)
    session.add(group_assoc)
    status_history = StatusHistory(
        status_type="Monitoring Status",
        status_value="Currently monitored",
        start_date=date(2024, 1, 1),
        end_date=None,
        reason="A1 behave seed status",
        target_id=well.id,
        target_table="thing",
    )
    session.add(status_history)
    session.commit()

    return well


def _seed_all(session):
    """Seed one public/private/draft row per relevant thing type, one
    draft Group with a project_area, and one standalone Location per
    status. Returns {seed_key: {"public": id, "private": id, "draft": id}}.
    """
    seed_ids = {}

    monitoring_group = Group(
        name="Water Level Network",
        description="A1 behave seed monitoring group",
        release_status="public",
    )
    session.add(monitoring_group)
    session.commit()

    for layer_id, thing_type in SIMPLE_THING_TYPE_LAYERS:
        seed_ids[layer_id] = {}
        for status in STATUSES:
            thing = _seed_thing_with_location(
                session, thing_type, status, f"A1 {layer_id} {status}"
            )
            seed_ids[layer_id][status] = thing.id

    seed_ids["water_wells"] = {}
    for status in STATUSES:
        well = _seed_water_well(
            session, status, f"A1 water well {status}", monitoring_group
        )
        seed_ids["water_wells"][status] = well.id

    seed_ids["project_areas"] = {}
    for status in STATUSES:
        group = Group(
            name=f"A1 project area {status}",
            description="A1 behave seed project area group",
            release_status=status,
            project_area=(
                "MULTIPOLYGON(((-107.2 33.6, -106.6 33.6, "
                "-106.6 34.2, -107.2 34.2, -107.2 33.6)))"
            ),
        )
        session.add(group)
        session.commit()
        seed_ids["project_areas"][status] = group.id

    seed_ids["locations"] = {}
    for status in STATUSES:
        location = Location(
            point="POINT(-106.0 34.5)",
            elevation=1600.0,
            release_status=status,
        )
        session.add(location)
        session.commit()
        seed_ids["locations"][status] = location.id

    # Materialized views are snapshots, not live queries -- the newly
    # seeded rows are invisible to them until refreshed.
    session.execute(text("SELECT public.refresh_materialized_views()"))
    session.commit()

    return seed_ids


def _teardown_a1_seed_data():
    """Delete every row these scenarios seed, by naming convention.

    Without this, Thing/Group rows from an earlier A1 scenario in the same
    behave run leak into a later scenario's absolute feature-count checks
    (e.g. the already-consistent-layers scenario). Registered via
    context.add_cleanup so it runs after the scenario regardless of
    pass/fail, without needing an environment.py hook.
    """
    with session_ctx() as session:
        session.execute(text("DELETE FROM thing WHERE name LIKE 'A1 %'"))
        session.execute(
            text(
                "DELETE FROM \"group\" WHERE name LIKE 'A1 %' OR name = 'Water Level Network'"
            )
        )
        session.commit()


def _ensure_head(context):
    command.upgrade(_alembic_config(), "head")
    with session_ctx() as session:
        context.seed_ids = _seed_all(session)
    context.add_cleanup(_teardown_a1_seed_data)


@given("a clean database state before the Sprint 1 migration")
def step_given_clean_database_state(context):
    command.downgrade(_alembic_config(), PRE_A1_REVISION)
    with session_ctx() as session:
        context.seed_ids = _seed_all(session)
    context.add_cleanup(_teardown_a1_seed_data)


@when("the Sprint 1 Alembic migration is applied")
def step_when_sprint1_alembic_migration_is_applied(context):
    command.upgrade(_alembic_config(), "head")


@then('each ogc_* view returns only records with release_status "public"')
def step_then_views_are_public_only(context):
    with session_ctx() as session:
        for relation, seed_key in VIEW_TO_SEED_KEY.items():
            ids = context.seed_ids[seed_key]
            for status in ("private", "draft"):
                count = session.execute(
                    text(f"SELECT COUNT(*) FROM {relation} WHERE id = :id"),
                    {"id": ids[status]},
                ).scalar()
                assert count == 0, (
                    f"{relation} exposed a {status} row (id={ids[status]}) "
                    "that should have been filtered out"
                )
            public_count = session.execute(
                text(f"SELECT COUNT(*) FROM {relation} WHERE id = :id"),
                {"id": ids["public"]},
            ).scalar()
            assert public_count == 1, f"{relation} is missing its public seed row"


@given("the Sprint 1 migration has been applied")
def step_given_sprint1_migration_has_been_applied(context):
    _ensure_head(context)


@when("the Sprint 1 migration downgrade is run")
def step_when_sprint1_migration_downgrade_is_run(context):
    context.downgrade_error = None
    try:
        command.downgrade(_alembic_config(), PRE_A1_REVISION)
    except Exception as exc:  # noqa: BLE001 -- surfaced via the next Then step
        context.downgrade_error = exc


@then(
    "each ogc_* view returns the same count of {status} records as before the migration"
)
def step_then_same_count_as_before_migration(context, status):
    assert (
        context.downgrade_error is None
    ), f"Downgrade raised an error before counts could be checked: {context.downgrade_error}"
    with session_ctx() as session:
        for relation, seed_key in VIEW_TO_SEED_KEY.items():
            if relation in NOT_PRESENT_BEFORE_A1:
                continue
            ids = context.seed_ids[seed_key]
            count = session.execute(
                text(f"SELECT COUNT(*) FROM {relation} WHERE id = :id"),
                {"id": ids[status]},
            ).scalar()
            assert count == 1, (
                f"{relation}: expected the seeded {status} row to be visible again "
                f"after downgrade (pre-A1 had no filter), got count={count}"
            )


@then("no database errors are raised")
def step_then_no_database_errors_are_raised(context):
    assert (
        context.downgrade_error is None
    ), f"Downgrade raised: {context.downgrade_error}"
    # Restore head immediately so later scenarios/features never run against
    # a downgraded schema even if a later step in this scenario fails.
    command.upgrade(_alembic_config(), "head")


def _get_items(context, layer_id, limit=200):
    response = context.client.get(f"/ogcapi/collections/{layer_id}/items?limit={limit}")
    assert (
        response.status_code == 200
    ), f"Unexpected status {response.status_code} for layer {layer_id}: {response.text}"
    return response.json()


@when("a public client requests items from each of the following layers:")
def step_when_public_client_requests_items_from_layers(context):
    context.layer_responses = {}
    for row in context.table:
        layer_id = row["layer-id"].strip()
        context.layer_responses[layer_id] = _get_items(context, layer_id)


def _layer_feature_ids(payload):
    ids = set()
    for feature in payload["features"]:
        feature_id = feature.get("id", feature.get("properties", {}).get("id"))
        ids.add(feature_id)
    return ids


@then('each response contains only records where release_status is "public"')
def step_then_each_response_contains_only_public(context):
    for layer_id, payload in context.layer_responses.items():
        seed_key = LAYER_ID_TO_SEED_KEY[layer_id]
        features = payload["features"]
        if features and "release_status" in features[0]["properties"]:
            for feature in features:
                assert (
                    feature["properties"]["release_status"] == "public"
                ), f"{layer_id} returned a non-public record: {feature['properties']}"
        else:
            ids_present = _layer_feature_ids(payload)
            public_id = context.seed_ids[seed_key]["public"]
            assert (
                public_id in ids_present
            ), f"{layer_id} is missing its public seed row"


@then('no response contains a record where release_status is "{status}"')
def step_then_no_response_contains_status(context, status):
    for layer_id, payload in context.layer_responses.items():
        seed_key = LAYER_ID_TO_SEED_KEY[layer_id]
        features = payload["features"]
        if features and "release_status" in features[0]["properties"]:
            for feature in features:
                assert (
                    feature["properties"]["release_status"] != status
                ), f"{layer_id} returned a {status} record: {feature['properties']}"
        else:
            ids_present = _layer_feature_ids(payload)
            excluded_id = context.seed_ids[seed_key][status]
            assert (
                excluded_id not in ids_present
            ), f"{layer_id} exposed its seeded {status} row (id={excluded_id})"


@given(
    'all 56 project_areas records have been updated from release_status "draft" to release_status "public"'
)
def step_given_56_project_areas_updated_to_public(context):
    publish_project_areas = importlib.import_module(
        "data_migrations.migrations.20260714_0001_publish_project_areas"
    )
    command.upgrade(_alembic_config(), "head")
    with session_ctx() as session:
        groups = [
            Group(
                name=f"A1 56-count project area {i}",
                description="A1 behave seed project area for the 56-row scenario",
                release_status="draft",
                project_area=(
                    "MULTIPOLYGON(((-107.0 33.0, -106.9 33.0, "
                    "-106.9 33.1, -107.0 33.1, -107.0 33.0)))"
                ),
            )
            for i in range(56)
        ]
        session.add_all(groups)
        session.commit()
        context.project_area_group_ids = [g.id for g in groups]

        publish_project_areas.run(session)


@when("a client requests features from the project_areas layer")
def step_when_client_requests_project_areas(context):
    context.response = context.client.get(
        "/ogcapi/collections/project_areas/items?limit=1000"
    )


@then("the response contains {count:d} features")
def step_then_response_contains_n_features(context, count):
    payload = context.response.json()
    matching = [
        f
        for f in payload["features"]
        if f.get("id", f.get("properties", {}).get("id"))
        in set(context.project_area_group_ids)
    ]
    assert len(matching) == count, (
        f"Expected {count} of this scenario's seeded project_areas features, "
        f"found {len(matching)}"
    )


@then("the response HTTP status is {status:d}")
def step_then_response_http_status_is(context, status):
    assert (
        context.response.status_code == status
    ), f"Unexpected status {context.response.status_code}, expected {status}"


@then('all returned features have release_status "public"')
def step_then_all_returned_features_are_public(context):
    payload = context.response.json()
    for feature in payload["features"]:
        if feature.get("id", feature.get("properties", {}).get("id")) not in set(
            context.project_area_group_ids
        ):
            continue
        assert (
            feature["properties"]["release_status"] == "public"
        ), f"Feature {feature.get('id')} was not public: {feature['properties']}"


def _seed_already_consistent_layers(session):
    """These 4 layers are asserted to be 100% public today -- unlike
    _seed_all(), only public rows are seeded here. Seeding private/draft
    rows into them would defeat the point of this scenario: proving the
    filter changes nothing because there was never anything to filter.
    """
    for layer_id, thing_type in SIMPLE_THING_TYPE_LAYERS:
        if layer_id not in ALREADY_CONSISTENT_LAYER_IDS:
            continue
        for i in range(3):
            _seed_thing_with_location(
                session, thing_type, "public", f"A1 already-consistent {layer_id} {i}"
            )


@given("the following layers were already filtering correctly before the migration:")
def step_given_already_consistent_layers(context):
    command.downgrade(_alembic_config(), PRE_A1_REVISION)
    with session_ctx() as session:
        _seed_already_consistent_layers(session)
        session.commit()
    context.add_cleanup(_teardown_a1_seed_data)

    context.already_consistent_counts = {}
    for row in context.table:
        layer_id = row["layer-id"].strip()
        payload = _get_items(context, layer_id, limit=500)
        context.already_consistent_counts[layer_id] = len(payload["features"])


@when("the Sprint 1 migration is applied")
def step_when_sprint1_migration_is_applied(context):
    command.upgrade(_alembic_config(), "head")


@then("each of those layers returns the same feature count as before the migration")
def step_then_same_feature_count_as_before(context):
    for layer_id, before_count in context.already_consistent_counts.items():
        payload = _get_items(context, layer_id, limit=500)
        after_count = len(payload["features"])
        assert (
            after_count == before_count
        ), f"{layer_id}: expected {before_count} features (unchanged), got {after_count}"


# ============= EOF =============================================
