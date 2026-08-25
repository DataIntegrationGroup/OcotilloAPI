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
"""Step definitions for A1 (public release_status filter on ogc_* views),
A2 (OGC server metadata placeholders), A11 (authenticated internal OGC
mount at /ogcapi-internal) and A13 (last_observation_date on the Group A
view template).

Only the @A1-, @A2-, @A11- and @A13-tagged scenarios in
ogc-cleanup-sprint1.feature are implemented here. The other tickets sharing
that feature file have no steps yet and stay undefined/dormant, per those
tickets' plans.
"""

import importlib
import os
from datetime import date
from unittest.mock import patch
from urllib.parse import urlparse

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
from core.permissions import INTERNAL_OGC_GROUP
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
from tests.features.environment import _alembic_config, reset_pygeoapi_reflection

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
    reset_pygeoapi_reflection()
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
    reset_pygeoapi_reflection()


@then("each of those layers returns the same feature count as before the migration")
def step_then_same_feature_count_as_before(context):
    for layer_id, before_count in context.already_consistent_counts.items():
        payload = _get_items(context, layer_id, limit=500)
        after_count = len(payload["features"])
        assert (
            after_count == before_count
        ), f"{layer_id}: expected {before_count} features (unchanged), got {after_count}"


# ---------------------------------------------------------------------------
# A11 -- authenticated internal OGC mount (/ogcapi-internal)
# ---------------------------------------------------------------------------
#
# tests/test_pygeoapi_mount.py's existing coverage and the "a functioning
# api" step above both only touch FastAPI's app.dependency_overrides, which
# has zero effect on ASGI middleware -- none of this codebase's existing
# auth-testing infrastructure reaches InternalOGCAuthMiddleware for free.
# The 401/403/200 scenarios below instead neutralize the ambient
# AUTHENTIK_DISABLE_AUTHENTICATION dev-bypass (set for the whole bdd-tests CI
# job) for the scenario's duration only, and control
# core.permissions.decode_token_payload's return value directly, since no
# real Authentik server is available in CI to issue a genuine JWT.


def _neutralize_authentik_bypass(context):
    """Temporarily force the dev-bypass off so InternalOGCAuthMiddleware's
    real 401/403 logic actually runs, restored unconditionally afterward so
    later scenarios relying on the global CI dev-bypass are unaffected.
    """
    original = os.environ.get("AUTHENTIK_DISABLE_AUTHENTICATION")
    os.environ["AUTHENTIK_DISABLE_AUTHENTICATION"] = "0"

    def _restore():
        if original is None:
            os.environ.pop("AUTHENTIK_DISABLE_AUTHENTICATION", None)
        else:
            os.environ["AUTHENTIK_DISABLE_AUTHENTICATION"] = original

    context.add_cleanup(_restore)


def _patch_decode_token_payload(context, groups):
    patcher = patch(
        "core.permissions.decode_token_payload", return_value={"groups": groups}
    )
    patcher.start()
    context.add_cleanup(patcher.stop)


def _teardown_a11_seed_data():
    with session_ctx() as session:
        session.execute(text("DELETE FROM thing WHERE name LIKE 'A11 %'"))
        session.commit()


@when("an unauthenticated client requests /ogcapi-internal/collections")
def step_when_unauthenticated_client_requests_internal_collections(context):
    _neutralize_authentik_bypass(context)
    context.response = context.client.get("/ogcapi-internal/collections")


@given('the client presents a valid token with role "{role}"')
def step_given_client_presents_token_with_role(context, role):
    _neutralize_authentik_bypass(context)
    _patch_decode_token_payload(context, groups=[role])
    context.auth_token = "a11-behave-test-token"


@when("the client requests /ogcapi-internal/collections")
def step_when_client_requests_internal_collections(context):
    headers = {"Authorization": f"Bearer {context.auth_token}"}
    context.response = context.client.get(
        "/ogcapi-internal/collections", headers=headers
    )


@given("an internal staff member with the required role is authenticated via Authentik")
def step_given_internal_staff_authenticated_via_authentik(context):
    _neutralize_authentik_bypass(context)
    _patch_decode_token_payload(context, groups=[INTERNAL_OGC_GROUP])
    context.auth_token = "a11-behave-test-token"


@when("the staff member requests /ogcapi-internal/collections")
def step_when_staff_member_requests_internal_collections(context):
    headers = {"Authorization": f"Bearer {context.auth_token}"}
    context.response = context.client.get(
        "/ogcapi-internal/collections", headers=headers
    )


@then("the response includes collections not available on the public /ogcapi endpoint")
def step_then_response_includes_internal_only_collections(context):
    payload = context.response.json()
    collections = payload.get("collections", [])
    assert collections, "internal endpoint returned no collections"
    for collection in collections:
        links = collection.get("links", [])
        assert any("/ogcapi-internal" in link.get("href", "") for link in links), (
            f"{collection.get('id')}: no self-link referencing /ogcapi-internal -- "
            "expected each internal collection representation to be reachable "
            "only via the internal mount, not the public /ogcapi endpoint"
        )


@given("an authenticated internal staff member")
def step_given_an_authenticated_internal_staff_member(context):
    # Relies on the ambient AUTHENTIK_DISABLE_AUTHENTICATION dev-bypass (set
    # for the whole CI job) rather than a real token -- this scenario is
    # about what the internal mount exposes, not auth semantics (covered
    # separately by the 401/403/200 scenarios above).
    with session_ctx() as session:
        context.a11_seed_ids = {}
        for status in STATUSES:
            thing = _seed_thing_with_location(
                session, "water well", status, f"A11 {status}"
            )
            context.a11_seed_ids[status] = thing.id
    context.add_cleanup(_teardown_a11_seed_data)


@when('the staff member requests items from the "{layer_id}" internal collection')
def step_when_staff_member_requests_internal_collection_items(context, layer_id):
    context.response = context.client.get(
        f"/ogcapi-internal/collections/{layer_id}/items?limit=500"
    )


@then('records with a release_status other than "public" are included in the response')
def step_then_non_public_records_included(context):
    payload = context.response.json()
    ids_present = _layer_feature_ids(payload)
    non_public_ids = {context.a11_seed_ids["private"], context.a11_seed_ids["draft"]}
    assert non_public_ids & ids_present, (
        "expected the internal collection to include the seeded private/draft "
        f"wells {non_public_ids}, got ids {ids_present}"
    )


@given("the /ogcapi-internal mount has been deployed")
def step_given_internal_mount_has_been_deployed(context):
    command.upgrade(_alembic_config(), "head")


@when("the database schema is inspected")
def step_when_database_schema_is_inspected(context):
    with session_ctx() as session:
        context.schema_relations = set(
            session.execute(
                text(
                    "SELECT c.relname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE c.relkind IN ('v', 'm') AND n.nspname = 'public'"
                )
            ).scalars()
        )


@then('the database schema contains relations prefixed with "{prefix}"')
def step_then_schema_contains_relations_prefixed(context, prefix):
    matching = {r for r in context.schema_relations if r.startswith(prefix)}
    assert matching, f"expected at least one relation prefixed {prefix!r}, found none"


@then("no ogc_internal_ relation is shared with the public /ogcapi endpoint")
def step_then_no_internal_relation_shared_with_public(context):
    internal = {r for r in context.schema_relations if r.startswith("ogc_internal_")}
    assert internal, "no ogc_internal_ relations found in the schema"
    for relation in internal:
        public_equivalent = relation.replace("ogc_internal_", "ogc_", 1)
        assert public_equivalent in context.schema_relations, (
            f"{relation} has no distinct public counterpart ({public_equivalent}) in "
            "the schema -- expected the two sets to coexist as separate relations"
        )


# "a client requests /ogcapi/collections" is defined in
# tests/features/steps/edr_water_data.py (functionally identical: GETs
# /ogcapi/collections and stashes context.response) -- reused rather than
# redefined here, since Behave raises AmbiguousStep on duplicate step text
# across files.


@then('no collection in the response has an id prefixed "{prefix}"')
def step_then_no_collection_id_prefixed(context, prefix):
    payload = context.response.json()
    offending = [c["id"] for c in payload["collections"] if c["id"].startswith(prefix)]
    assert not offending, f"found collections with id prefixed {prefix!r}: {offending}"


# ---------------------------------------------------------------------------
# A16/A17/A18 -- Layers hidden from the public catalog, backing relations kept
# ---------------------------------------------------------------------------


@given(
    "avg_tds_wells and latest_depth_to_water_wells have been removed from the "
    "service catalog"
)
@given("the locations entry has been removed from the service configuration")
@given("the other_things view has at least one reference in the application codebase")
def step_given_layer_hidden_from_public_catalog(context):
    # No-op marker: the catalog is core/pygeoapi-config.yml and
    # core.pygeoapi.THING_COLLECTIONS, both artifacts under test rather than
    # runtime state to arrange. Same treatment as the A1/A2/A11 givens.
    pass


@then("the response does not include a collection with id {collection_id}")
def step_then_response_excludes_collection_id(context, collection_id):
    payload = context.response.json()
    ids = {collection["id"] for collection in payload["collections"]}
    assert collection_id not in ids, (
        f"{collection_id} is still published on the public catalog; "
        f"collections: {sorted(ids)}"
    )


@then("the materialized view for {layer_id} exists in the database schema")
def step_then_matview_for_layer_exists(context, layer_id):
    relation = f"ogc_{layer_id}"
    assert relation in context.schema_relations, (
        f"{relation} is missing -- A16 hides the layer from the catalog but "
        "keeps its materialized view for internal use"
    )


@then("the locations table still exists")
def step_then_locations_table_still_exists(context):
    # context.schema_relations covers views and materialized views only, so
    # the base table needs its own lookup.
    with session_ctx() as session:
        relkind = session.execute(
            text(
                "SELECT c.relkind FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'location'"
            )
        ).scalar_one_or_none()
    assert relkind == "r", (
        "the location table is missing -- A17 hides the layer from the "
        f"catalog but keeps the underlying table (relkind={relkind!r})"
    )


def _assert_other_things_view_exists(context, relation):
    assert relation in context.schema_relations, (
        f"{relation} is missing -- A18 hides other_things from the public "
        "catalog but /ogcapi-internal still serves the layer"
    )


@then("the other_things backing view still exists in the database schema")
def step_then_other_things_view_still_exists(context):
    _assert_other_things_view_exists(context, "ogc_other_things")


@then("the internal other_things backing view still exists in the database schema")
def step_then_internal_other_things_view_still_exists(context):
    _assert_other_things_view_exists(context, "ogc_internal_other_things")


# ---------------------------------------------------------------------------
# A2 -- Replace OGC server metadata placeholders in pygeoapi-config.yml
# ---------------------------------------------------------------------------


@given("the service configuration has been updated with accurate metadata")
def step_given_service_metadata_updated(context):
    # No-op marker: core/pygeoapi-config.yml is the artifact under test, so
    # there is no runtime state to arrange. Mirrors how the A1/A11 givens
    # treat already-applied state.
    pass


@when("a client requests the /ogcapi landing page as JSON, as HTML, and as OpenAPI")
def step_when_request_landing_page_all_formats(context):
    context.metadata_responses = {
        "landing page (JSON)": context.client.get("/ogcapi", params={"f": "json"}),
        "landing page (HTML)": context.client.get("/ogcapi", params={"f": "html"}),
        "OpenAPI document": context.client.get("/ogcapi/openapi"),
    }
    for label, response in context.metadata_responses.items():
        assert (
            response.status_code == 200
        ), f"{label} returned {response.status_code}, expected 200"


@then('no response body contains an "{needle}" string')
def step_then_no_response_contains(context, needle):
    offending = [
        label
        for label, response in context.metadata_responses.items()
        if needle in response.text
    ]
    assert not offending, f"{needle!r} still present in: {', '.join(offending)}"


@when("a client requests the /ogcapi OpenAPI document")
def step_when_request_openapi_document(context):
    context.response = context.client.get("/ogcapi/openapi")
    assert (
        context.response.status_code == 200
    ), f"/ogcapi/openapi returned {context.response.status_code}, expected 200"


def _openapi_metadata_field(info, field):
    # pygeoapi maps metadata.provider onto OpenAPI info.contact and
    # metadata.contact onto the x-ogc-serviceContact extension
    # (pygeoapi/openapi.py gen_contact) -- neither is on the JSON landing page.
    contact = info["contact"]
    service_contact = contact["x-ogc-serviceContact"]
    if field == "provider_url":
        return contact["url"]
    if field == "contact_name":
        return service_contact["name"]
    if field == "contact_email":
        return service_contact["emails"][0]["value"]
    raise KeyError(f"unmapped metadata field {field!r}")


@then("the service metadata fields match the following values:")
def step_then_service_metadata_fields_match(context):
    info = context.response.json()["info"]
    mismatches = []
    for row in context.table:
        field = row["field"]
        expected = row["expected-value"]
        actual = _openapi_metadata_field(info, field)
        if actual != expected:
            mismatches.append(f"{field}: expected {expected!r}, got {actual!r}")
    assert not mismatches, "; ".join(mismatches)


@then("the terms of service URL resolves to the service disclaimer page")
def step_then_terms_of_service_resolves(context):
    terms_url = context.response.json()["info"]["termsOfService"]
    parsed = urlparse(terms_url)
    assert parsed.scheme in (
        "http",
        "https",
    ), f"termsOfService {terms_url!r} is not an absolute http(s) URL"
    assert (
        parsed.path == "/disclaimer"
    ), f"termsOfService {terms_url!r} does not point at /disclaimer"

    response = context.client.get(parsed.path)
    assert response.status_code == 200, (
        f"advertised termsOfService {terms_url!r} returned "
        f"{response.status_code} -- a 404 is no better than a placeholder"
    )
    assert (
        "New Mexico Bureau of Geology and Mineral Resources" in response.text
    ), f"{terms_url!r} resolved but does not look like the disclaimer page"


# ---------------------------------------------------------------------------
# A13 -- last_observation_date on the Group A view template
# ---------------------------------------------------------------------------

# Every Group A layer the A13 scenarios name, plus water_wells, which is not in
# SIMPLE_THING_TYPE_LAYERS because the A1 scenarios seed it with a full
# observation/chemistry chain rather than a bare Location + Thing.
A13_LAYER_THING_TYPES = {"water_wells": "water well", **dict(SIMPLE_THING_TYPE_LAYERS)}

# Dates the filter scenario splits on: one comfortably before its 2021-01-01
# cutoff, one comfortably after.
A13_STALE_DATE = "2019-06-01"
A13_RECENT_DATE = "2023-06-01"


def _seed_thing_with_observation(session, thing_type, name, observation_date=None):
    """A public thing of `thing_type`, optionally with one public observation.

    `observation_date` is a plain YYYY-MM-DD string; it is stored at midday UTC
    so the view's UTC-date cast cannot land on the neighbouring day.
    """
    thing = _seed_thing_with_location(session, thing_type, "public", name)
    if observation_date is None:
        return thing

    field_event = FieldEvent(
        thing_id=thing.id,
        event_date=f"{observation_date}T12:00:00Z",
        notes="A13 behave seed field event",
        release_status="public",
    )
    session.add(field_event)
    session.commit()

    field_activity = FieldActivity(
        field_event_id=field_event.id,
        activity_type="groundwater level",
        notes="A13 behave seed field activity",
        release_status="public",
    )
    session.add(field_activity)
    session.commit()

    sample = Sample(
        field_activity_id=field_activity.id,
        sample_date=f"{observation_date}T12:00:00Z",
        sample_name=f"A13 sample {thing.id}",
        sample_matrix="water",
        sample_method="Steel-tape measurement",
        qc_type="Normal",
        notes="A13 behave seed sample",
        release_status="public",
    )
    session.add(sample)
    session.commit()

    observation = Observation(
        observation_datetime=f"{observation_date}T12:00:00Z",
        sample_id=sample.id,
        parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
        release_status="public",
        value=12.0,
        unit="ft",
        measuring_point_height=1.0,
        groundwater_level_reason="Water level not affected",
    )
    session.add(observation)
    session.commit()

    return thing


def _get_item(context, layer_id, feature_id):
    response = context.client.get(f"/ogcapi/collections/{layer_id}/items/{feature_id}")
    assert response.status_code == 200, (
        f"Unexpected status {response.status_code} for {layer_id}/{feature_id}: "
        f"{response.text}"
    )
    return response.json()


@when("a client requests items from each of the following layers:")
def step_when_client_requests_items_from_layers(context):
    context.layer_responses = {}
    for row in context.table:
        layer_id = row["layer-id"].strip()
        context.layer_responses[layer_id] = _get_items(context, layer_id)


@then("each feature includes a last_observation_date property")
def step_then_each_feature_includes_last_observation_date(context):
    for layer_id, payload in context.layer_responses.items():
        # Several Group A thing types carry no seeded rows in the behave
        # database, and an empty feature list would let a missing column pass
        # unnoticed -- so the layer's own queryables are checked as well.
        queryables = context.client.get(f"/ogcapi/collections/{layer_id}/queryables")
        assert queryables.status_code == 200, (
            f"queryables for {layer_id} returned {queryables.status_code}: "
            f"{queryables.text}"
        )
        advertised = queryables.json().get("properties", {})
        assert "last_observation_date" in advertised, (
            f"{layer_id} does not advertise last_observation_date: "
            f"{sorted(advertised)}"
        )

        for feature in payload["features"]:
            assert "last_observation_date" in feature["properties"], (
                f"{layer_id} feature {feature.get('id')} has no "
                f"last_observation_date property: {sorted(feature['properties'])}"
            )


@given(
    "monitoring locations with no linked observations exist in each of the following layers:"
)
def step_given_things_without_observations(context):
    context.a13_unobserved_ids = {}
    with session_ctx() as session:
        for row in context.table:
            layer_id = row["layer-id"].strip()
            thing_type = A13_LAYER_THING_TYPES[layer_id]
            thing = _seed_thing_with_observation(
                session, thing_type, f"A13 unobserved {layer_id}"
            )
            context.a13_unobserved_ids[layer_id] = thing.id


@when("a client requests those features")
def step_when_client_requests_those_features(context):
    context.a13_unobserved_features = {
        layer_id: _get_item(context, layer_id, feature_id)
        for layer_id, feature_id in context.a13_unobserved_ids.items()
    }


@then("each feature's last_observation_date property is null")
def step_then_last_observation_date_is_null(context):
    for layer_id, feature in context.a13_unobserved_features.items():
        value = feature["properties"]["last_observation_date"]
        assert value is None, (
            f"{layer_id} feature {feature.get('id')} has last_observation_date "
            f"{value!r}; a thing with no observations must read null"
        )


@given(
    "each of the following Group A layers has features with last_observation_date "
    'values "{stale_date}" and "{recent_date}":'
)
def step_given_layers_with_stale_and_recent_observations(
    context, stale_date, recent_date
):
    context.a13_stale_ids = {}
    context.a13_recent_ids = {}
    with session_ctx() as session:
        for row in context.table:
            layer_id = row["layer-id"].strip()
            thing_type = A13_LAYER_THING_TYPES[layer_id]
            stale = _seed_thing_with_observation(
                session, thing_type, f"A13 stale {layer_id}", stale_date
            )
            recent = _seed_thing_with_observation(
                session, thing_type, f"A13 recent {layer_id}", recent_date
            )
            context.a13_stale_ids[layer_id] = stale.id
            context.a13_recent_ids[layer_id] = recent.id


@when("a client requests items from each of those layers with filter")
def step_when_client_requests_layers_with_filter(context):
    cql = context.text.strip()
    context.layer_responses = {}
    for layer_id in context.a13_recent_ids:
        response = context.client.get(
            f"/ogcapi/collections/{layer_id}/items",
            params={"filter": cql, "filter-lang": "cql2-text", "limit": 200},
        )
        assert response.status_code == 200, (
            f"Filtered request on {layer_id} returned {response.status_code}: "
            f"{response.text}"
        )
        context.layer_responses[layer_id] = response.json()


@then(
    'only features with a last_observation_date of "{recent_date}" are returned '
    "from each layer"
)
def step_then_only_recent_features_returned(context, recent_date):
    cutoff = date.fromisoformat("2021-01-01")
    for layer_id, payload in context.layer_responses.items():
        returned_ids = _layer_feature_ids(payload)
        recent_id = context.a13_recent_ids[layer_id]
        stale_id = context.a13_stale_ids[layer_id]

        assert (
            recent_id in returned_ids
        ), f"{layer_id} dropped its {recent_date} feature (id={recent_id})"
        assert stale_id not in returned_ids, (
            f"{layer_id} returned its {A13_STALE_DATE} feature (id={stale_id}) "
            "through a filter that excludes it"
        )

        for feature in payload["features"]:
            value = feature["properties"]["last_observation_date"]
            assert value is not None, (
                f"{layer_id} feature {feature.get('id')} passed the filter with "
                "a null last_observation_date"
            )
            assert date.fromisoformat(value[:10]) > cutoff, (
                f"{layer_id} feature {feature.get('id')} has last_observation_date "
                f"{value!r}, which the filter should have excluded"
            )


# ============= EOF =============================================
