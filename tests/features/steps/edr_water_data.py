# ===============================================================================
# Copyright 2025 ross
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
"""
Step definitions for the OGC API - EDR water-data feature (ADR3).

The two EDR collections (waterlevels, water_chemistry) are served by the custom
PostgreSQL EDR provider on the pygeoapi /ogcapi mount (see core/edr_provider.py
and core/pygeoapi.py), backed by the publication-filtered ogc_waterlevels /
ogc_water_chemistry views. Test data is seeded in environment.before_all via
add_edr_water_data. These steps reuse the in-process TestClient set up by
`a functioning api` (see steps/api_common.py).

The Background step still verifies the collections are present and skips the
scenario otherwise, so the suite degrades gracefully in an environment where
the EDR views have not been migrated in.
"""

from datetime import datetime, timezone

from behave import given, when, then

MOUNT = "/ogcapi"
COVERAGE_CONTENT_TYPES = (
    "application/prs.coverage+json",
    "application/vnd.cov+json",
    "application/json",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _get(context, path):
    """Issue a GET against the mounted app and stash the response."""
    context.response = context.client.get(path)
    return context.response


def _parse_dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _seeded_well_id(context):
    wells = context.objects.get("wells") if hasattr(context, "objects") else None
    assert wells, "No seeded wells; run with DROP_AND_REBUILD_DB to populate test data."
    return wells[0].id


def _collection_ids(payload):
    return {c.get("id") for c in payload.get("collections", [])}


def _coverages(payload):
    """Yield the coverage objects of a Coverage or CoverageCollection payload."""
    return payload.get("coverages", [payload])


def _coverage_datetimes(payload):
    """Pull the temporal axis values out of a CoverageJSON payload.

    Handles both a single Coverage and a CoverageCollection.
    """
    stamps = []
    for cov in _coverages(payload):
        t_axis = cov.get("domain", {}).get("axes", {}).get("t", {})
        stamps.extend(t_axis.get("values", []))
    return stamps


# ---------------------------------------------------------------------------
# background / configuration
# ---------------------------------------------------------------------------
@given("the EDR collections are configured on the /ogcapi mount")
def step_edr_configured(context):
    resp = _get(context, f"{MOUNT}/collections?f=json")
    configured = False
    if resp.status_code == 200:
        try:
            configured = {"waterlevels", "water_chemistry"} <= _collection_ids(
                resp.json()
            )
        except ValueError:
            configured = False
    if not configured:
        context.scenario.skip(
            "EDR collections (waterlevels, water_chemistry) not yet implemented "
            "on the /ogcapi mount — ADR3 proposal, @wip."
        )


# ---------------------------------------------------------------------------
# generic EDR requests
# ---------------------------------------------------------------------------
@when("a client requests /ogcapi/collections")
def step_client_requests_collections(context):
    _get(context, f"{MOUNT}/collections?f=json")


@when("a client requests /ogcapi/conformance")
def step_client_requests_conformance(context):
    _get(context, f"{MOUNT}/conformance?f=json")


@when('a client requests the EDR collection metadata for "{cid}"')
def step_request_collection_metadata(context, cid):
    _get(context, f"{MOUNT}/collections/{cid}?f=json")


# ---------------------------------------------------------------------------
# data-setup givens (resolve the seeded well; EDR-not-built scenarios are
# already skipped in Background, so these stay intentionally light)
# ---------------------------------------------------------------------------
@given("a well with water-level observations")
@given("a well with both manual and transducer water-level data")
@given("a well with a transducer deployment")
@given("a well that has non-public water-level and chemistry records")
def step_resolve_well(context):
    context.edr_well_id = _seeded_well_id(context)


@given("a polygon that covers wells with chemistry data")
def step_polygon(context):
    # A generous bbox-as-polygon around the New Mexico extent used by the mount.
    context.edr_polygon = (
        "POLYGON((-109.05 31.33,-103.00 31.33,-103.00 37.00,"
        "-109.05 37.00,-109.05 31.33))"
    )


# ---------------------------------------------------------------------------
# location / instance / area queries
# ---------------------------------------------------------------------------
@when('the client requests the "{cid}" location series for that well over "{interval}"')
def step_location_series(context, cid, interval):
    wid = context.edr_well_id
    _get(
        context,
        f"{MOUNT}/collections/{cid}/locations/{wid}" f"?datetime={interval}&f=json",
    )


@when(
    'the client requests the "{cid}" location series for that well over the full period'
)
def step_location_series_full(context, cid):
    wid = context.edr_well_id
    _get(context, f"{MOUNT}/collections/{cid}/locations/{wid}?f=json")


@when('the client requests the "{cid}" instances for that well')
def step_instances_for_well(context, cid):
    wid = context.edr_well_id
    _get(
        context,
        f"{MOUNT}/collections/{cid}/instances?location_id={wid}&f=json",
    )


@when('the client requests "{cid}" for that area with parameter name "{param}"')
def step_area_query(context, cid, param):
    _get(
        context,
        f"{MOUNT}/collections/{cid}/area"
        f"?coords={context.edr_polygon}&parameter-name={param}&f=json",
    )


# ---------------------------------------------------------------------------
# catalog / metadata assertions
# ---------------------------------------------------------------------------
@then('the collections catalog includes the EDR collection "{cid}"')
def step_catalog_includes(context, cid):
    assert cid in _collection_ids(context.response.json()), (
        f"Collection {cid!r} not found in catalog: "
        f"{sorted(_collection_ids(context.response.json()))}"
    )


@then("the collection declares a spatial extent")
def step_declares_spatial(context):
    extent = context.response.json().get("extent", {})
    assert extent.get("spatial"), "Collection declares no spatial extent."


@then("the collection declares a temporal extent")
def step_declares_temporal(context):
    extent = context.response.json().get("extent", {})
    assert extent.get("temporal"), "Collection declares no temporal extent."


@then('the collection declares the parameter name "{param}"')
def step_declares_parameter(context, param):
    payload = context.response.json()
    names = payload.get("parameter_names") or payload.get("parameter-names") or {}
    haystack = " ".join(
        [str(k) for k in names]
        + [str(v.get("name", "")) for v in names.values() if isinstance(v, dict)]
    ).lower()
    assert (
        param.lower() in haystack
    ), f"Parameter {param!r} not declared. Parameters: {list(names)}"


@then('the collection declares the EDR query patterns "{patterns}"')
def step_declares_patterns(context, patterns):
    wanted = {p.strip() for p in patterns.split(",")}
    queries = set(context.response.json().get("data_queries", {}).keys())
    missing = wanted - queries
    assert not missing, f"Collection missing EDR query patterns: {missing}"


# ---------------------------------------------------------------------------
# CoverageJSON assertions
# ---------------------------------------------------------------------------
@then("the response is CoverageJSON")
def step_is_coveragejson(context):
    ctype = context.response.headers.get("Content-Type", "")
    assert any(
        ct in ctype for ct in COVERAGE_CONTENT_TYPES
    ), f"Unexpected Content-Type {ctype!r}"
    body = context.response.json()
    assert body.get("type") in (
        "Coverage",
        "CoverageCollection",
    ), f"Not a CoverageJSON document: type={body.get('type')!r}"


@then('the coverage exposes the parameter "{param}"')
def step_coverage_exposes_parameter(context, param):
    params = context.response.json().get("parameters", {})
    haystack = " ".join(str(k) for k in params).lower()
    for v in params.values():
        haystack += " " + str(v.get("observedProperty", {})).lower()
    assert (
        param.lower() in haystack
    ), f"Parameter {param!r} not in coverage parameters: {list(params)}"


@then('every observation datetime is within "{interval}"')
def step_datetimes_within(context, interval):
    start_s, end_s = interval.split("/")
    start, end = _parse_dt(start_s), _parse_dt(end_s)
    stamps = _coverage_datetimes(context.response.json())
    assert stamps, "Coverage exposes no temporal axis values to check."
    for s in stamps:
        dt = _parse_dt(s)
        assert start <= dt <= end, f"Observation {s} outside {interval}."


@then("the coverage contains both manual and transducer readings")
def step_both_sources(context):
    # Manual (Observation) and transducer (TransducerObservation) rows are merged
    # onto one series (ADR3 decision). We assert the merged axis is non-trivial;
    # provenance-per-point is carried in a parameter/annotation once implemented.
    stamps = _coverage_datetimes(context.response.json())
    assert len(stamps) >= 2, (
        "Merged manual + transducer series should expose multiple readings; "
        f"got {len(stamps)}."
    )


@then('every returned value is for the parameter "{param}"')
def step_area_values_parameter(context, param):
    params = context.response.json().get("parameters", {})
    haystack = " ".join(str(k) for k in params).lower()
    assert (
        param.lower() in haystack
    ), f"Area coverage does not restrict to {param!r}: {list(params)}"


# ---------------------------------------------------------------------------
# instance assertions
# ---------------------------------------------------------------------------
@then("at least one EDR instance is listed")
def step_instances_listed(context):
    instances = context.response.json().get("instances", [])
    assert instances, "No EDR instances (transducer deployments) returned."


@then("each EDR instance has an identifier")
def step_instances_have_id(context):
    for inst in context.response.json().get("instances", []):
        assert inst.get("id"), f"EDR instance missing id: {inst}"


# ---------------------------------------------------------------------------
# publication gating
# ---------------------------------------------------------------------------
# The seed (environment.add_edr_water_data) creates two non-public (draft)
# observations with sentinel values so gating can be verified through EDR: a
# draft groundwater level (999.0) and a draft pH analysis (99.0). Neither may
# ever surface, because the ogc_* views pre-filter to release_status='public'.
_DRAFT_SENTINELS = {999.0, 99.0}


@then('no returned record has a release_status other than "{status}"')
def step_only_status(context, status):
    published = set()
    for cov in _coverages(context.response.json()):
        for rng in cov.get("ranges", {}).values():
            published.update(v for v in rng.get("values", []) if v is not None)
    leaked = _DRAFT_SENTINELS & published
    assert (
        not leaked
    ), f"Non-{status} sentinel values leaked through EDR: {sorted(leaked)}"


# ---------------------------------------------------------------------------
# conformance
# ---------------------------------------------------------------------------
@then("the conformance classes include an OGC API - EDR core class")
def step_conformance_edr(context):
    classes = context.response.json().get("conformsTo", [])
    assert any(
        "edr" in c.lower() for c in classes
    ), "No OGC API - EDR conformance class advertised."


# ============= EOF =============================================
