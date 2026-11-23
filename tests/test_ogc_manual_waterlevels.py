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
"""The manual_waterlevels OGC API - EDR collection.

These tests hold the collection to its contract,
docs/ogc-waterlevels-data-contract.md. The rules worth protecting are:

- only public readings from public wells are published on /ogcapi, while the
  internal mirror keeps carrying non-public ones;
- only hand-measured readings appear -- no transducer (continuous) data;
- a null level is published only with its reason;
- depth below ground surface follows the measuring-point convention
  (value minus measuring point height, a null height counting as 0);
- the reason parameter's categories come from the lexicon's
  groundwater level reason terms, which the contract defers to.
"""

from datetime import datetime
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
from db import FieldActivity, FieldEvent, Observation, Sample
from db.engine import session_ctx
from tests import get_parameter_id, override_authentication

pytestmark = pytest.mark.skipif(
    find_spec("pygeoapi") is None,
    reason="pygeoapi is not installed in this environment",
)


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


def test_ogc_manual_waterlevels_excludes_readings_from_a_non_public_well(
    water_well_thing, groundwater_level_observation
):
    """A well that is not public publishes no water levels, even public ones.

    ogc_manual_waterlevels used to filter on the reading's own release_status alone,
    so a draft or private well still published its public readings -- with the
    well's name and coordinates attached. ogc_water_chemistry already required
    the parent thing to be public; baba91fe5e83 brought water levels onto the
    same rule.
    """
    # The views' id is the observation's; a well's readings are found by thing_id.
    thing = {"tid": water_well_thing.id}
    view = {"vid": groundwater_level_observation.id}

    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.execute(
            text("UPDATE thing SET release_status = 'draft' WHERE id = :tid"),
            thing,
        )
        session.commit()

        public_rows = session.execute(
            text("SELECT id FROM ogc_manual_waterlevels WHERE id = :vid"),
            view,
        ).all()
        assert not public_rows, "a non-public well leaked a reading to /ogcapi"

        # The internal mount is where staff see non-public records; it must
        # keep carrying them.
        internal_rows = session.execute(
            text("SELECT id FROM ogc_internal_manual_waterlevels WHERE id = :vid"),
            view,
        ).all()
        assert internal_rows, "the internal mirror stopped carrying the reading"

        # Public well, public reading: published again.
        session.execute(
            text("UPDATE thing SET release_status = 'public' WHERE id = :tid"),
            thing,
        )
        session.commit()

        assert session.execute(
            text("SELECT id FROM ogc_manual_waterlevels WHERE id = :vid"),
            view,
        ).all()


def test_ogc_manual_waterlevel_feature_collection_shape(
    ogc_client, location, water_well_thing, thing_id_link, groundwater_level_observation
):
    """Test that the manual water level feature collection has the correct shape."""
    # make the observation public for external visibility
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )

        session.execute(
            text("UPDATE thing_id_link SET release_status = 'public' WHERE id = :tid"),
            {"tid": thing_id_link.id},
        )

        formation_description = session.execute(
            text("SELECT definition FROM lexicon_term WHERE term = :code"),
            {"code": water_well_thing.formation_completion_code},
        ).scalar_one()

        session.commit()

    response = ogc_client.get("/ogcapi/collections/manual_waterlevels/locations")
    assert response.status_code == 200

    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)
    assert len(data["features"]) == 1

    feature = data["features"][0]
    assert feature["id"] == water_well_thing.id
    assert feature["type"] == "Feature"
    assert "geometry" in feature
    assert "properties" in feature

    geometry = feature["geometry"]
    assert geometry["type"] == "Point"
    assert isinstance(geometry["coordinates"], list)
    # GeoJSON is [longitude, latitude]; Location.latlon is (latitude, longitude).
    latitude, longitude = location.latlon
    assert geometry["coordinates"] == pytest.approx([longitude, latitude])

    properties = feature["properties"]
    assert properties["name"] == water_well_thing.name
    assert properties["ground_surface_elevation"] == location.elevation
    assert properties["ground_surface_elevation_units"] == "m"
    assert properties["vertical_datum"] == "NAVD88"
    assert properties["well_depth"] == water_well_thing.well_depth
    assert properties["well_depth_units"] == "ft"
    assert properties["geologic_formation"] == {
        "code": water_well_thing.formation_completion_code,
        "description": formation_description,
    }
    assert properties["alternate_ids"] == [
        {
            "id": thing_id_link.alternate_id,
            "relation": thing_id_link.relation,
            "organization": thing_id_link.alternate_organization,
        }
    ]


def _lexicon_definitions(category: str) -> dict[str, str]:
    """``{term: definition}`` for one lexicon category, read from the database.

    The water-level contract defers to the lexicon for the reason categories,
    so the database -- not a copy in this file -- is what the response must
    match. No order is implied: lexicon_term has no position column.
    """
    with session_ctx() as session:
        rows = session.execute(
            text(
                "SELECT t.term, t.definition "
                "FROM lexicon_term t "
                "JOIN lexicon_term_category_association a ON a.term_id = t.id "
                "JOIN lexicon_category c ON c.id = a.category_id "
                "WHERE c.name = :category"
            ),
            {"category": category},
        ).all()
    return {term: definition for term, definition in rows}


def _assert_categories_match_lexicon(categories: list[dict], category: str) -> None:
    """A categorical parameter's categories are exactly the lexicon's terms.

    Each category's id and label are the term. A description appears only
    where the lexicon's definition says more than the term itself, and then
    it is that definition.
    """
    ids = [c["id"] for c in categories]
    assert len(ids) == len(set(ids)), f"duplicate categories: {ids}"

    definitions = _lexicon_definitions(category)
    assert definitions, f"lexicon category {category!r} has no terms"
    assert set(ids) == set(definitions), (
        f"missing from response: {sorted(set(definitions) - set(ids))}; "
        f"not in lexicon: {sorted(set(ids) - set(definitions))}"
    )

    for c in categories:
        assert c["label"]["en"] == c["id"]
        definition = definitions[c["id"]]
        if definition == c["id"]:
            assert (
                "description" not in c
            ), f"{c['id']!r} repeats its term as a description"
        else:
            assert c["description"]["en"] == definition


def test_ogc_manual_waterlevel_coverage_collection_shape(
    ogc_client, location, water_well_thing, groundwater_level_observation
):
    """Test that the manual water level coverage collection has the correct shape."""
    # make the observation public for external visibility
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

    response = ogc_client.get(
        f"/ogcapi/collections/manual_waterlevels/locations/{water_well_thing.id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "CoverageCollection"
    assert data["domainType"] == "PointSeries"

    # ----------------------------------------------------------- parameters
    parameters = data["parameters"]
    assert sorted(parameters.keys()) == sorted(
        ["groundwater level below ground surface", "groundwater level reason"]
    )

    level = parameters["groundwater level below ground surface"]
    assert level["type"] == "Parameter"
    assert level["description"]["en"] == (
        "Depth from the ground surface down to the water table, measured by hand during a site visit. Larger values mean the water table is further below the surface."
    )
    assert level["observedProperty"]["id"] == "groundwater level below ground surface"
    assert (
        level["observedProperty"]["label"]["en"]
        == "Groundwater level below ground surface"
    )
    assert level["unit"]["symbol"] == "ft"
    assert level["unit"]["label"]["en"] == "ft"

    reason = parameters["groundwater level reason"]
    assert reason["type"] == "Parameter"
    assert reason["description"]["en"] == (
        "The reason/qualifier for the recorded groundwater level."
    )
    assert reason["observedProperty"]["id"] == "groundwater level reason"
    assert reason["observedProperty"]["label"]["en"] == "Groundwater level reason"
    # A categorical parameter carries no unit in the contract.
    assert "unit" not in reason

    categories = reason["observedProperty"]["categories"]
    _assert_categories_match_lexicon(categories, "groundwater_level_reason")

    # ------------------------------------------------------------ coverages
    coverages = data["coverages"]
    assert len(coverages) == 1
    coverage = coverages[0]
    assert coverage["type"] == "Coverage"
    # Coverage ids are strings, unlike the integer feature ids from /locations.
    assert coverage["id"] == str(water_well_thing.id)

    # --------------------------------------------------------------- domain
    domain = coverage["domain"]
    assert domain["type"] == "Domain"
    assert domain["domainType"] == "PointSeries"

    latitude, longitude = location.latlon
    axes = domain["axes"]
    assert axes["x"]["values"] == pytest.approx([longitude])
    assert axes["y"]["values"] == pytest.approx([latitude])

    t_values = axes["t"]["values"]
    assert len(t_values) == 1
    assert datetime.fromisoformat(t_values[0]) == datetime.fromisoformat(
        groundwater_level_observation.observation_datetime
    )

    assert domain["referencing"] == [
        {
            "coordinates": ["x", "y"],
            "system": {
                "type": "GeographicCRS",
                "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
            },
        },
        {
            "coordinates": ["t"],
            "system": {"type": "TemporalRS", "calendar": "Gregorian"},
        },
    ]

    # --------------------------------------------------------------- ranges
    ranges = coverage["ranges"]
    assert sorted(ranges.keys()) == sorted(parameters.keys())

    # value (10.0 ft) minus the reading's measuring point height (5.0 ft)
    level_range = ranges["groundwater level below ground surface"]
    assert level_range["type"] == "NdArray"
    assert level_range["dataType"] == "float"
    assert level_range["axisNames"] == ["t"]
    assert level_range["shape"] == [len(t_values)]
    assert level_range["values"] == [
        groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    ]

    reason_range = ranges["groundwater level reason"]
    assert reason_range["type"] == "NdArray"
    assert reason_range["dataType"] == "string"
    assert reason_range["axisNames"] == ["t"]
    assert reason_range["shape"] == [len(t_values)]
    assert reason_range["values"] == [
        groundwater_level_observation.groundwater_level_reason
    ]


def test_ogc_manual_waterlevels_collection_lists_parameters(
    ogc_client, water_well_thing, groundwater_level_observation
):
    """The collection page lists both parameters; only the level has a unit,
    and only the reason has categories (from the lexicon)."""
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

    response = ogc_client.get("/ogcapi/collections/manual_waterlevels")

    assert response.status_code == 200
    parameter_names = response.json()["parameter_names"]
    assert set(parameter_names) == {
        "groundwater level below ground surface",
        "groundwater level reason",
    }
    level = parameter_names["groundwater level below ground surface"]
    assert level["unit"]["symbol"]["value"] == "ft"
    assert "categories" not in level["observedProperty"]

    reason = parameter_names["groundwater level reason"]
    assert "unit" not in reason
    _assert_categories_match_lexicon(
        reason["observedProperty"]["categories"], "groundwater_level_reason"
    )


def test_ogc_manual_waterlevels_schema_lists_reason_values(
    ogc_client, water_well_thing, groundwater_level_observation
):
    """/schema lists the reason's allowed values as a JSON Schema enum."""
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

    response = ogc_client.get("/ogcapi/collections/manual_waterlevels/schema")

    assert response.status_code == 200
    properties = response.json()["properties"]
    assert set(properties["groundwater level reason"]["enum"]) == set(
        _lexicon_definitions("groundwater_level_reason")
    )
    assert "enum" not in properties["groundwater level below ground surface"]
    assert properties["groundwater level below ground surface"]["type"] == "number"


def test_ogc_manual_waterlevels_instances_is_empty_list(
    ogc_client, water_well_thing, groundwater_level_observation
):
    response = ogc_client.get("/ogcapi/collections/manual_waterlevels/instances")
    assert response.status_code == 200
    assert response.json()["instances"] == []


# --------------------
# TEST VIEWS OGC_MANUAL_WATERLEVELS DEPEND ON
# --------------------


def test_ogc_manual_waterlevels_view(
    location,
    water_well_thing,
    thing_id_link,
    groundwater_level_observation,
):
    """
    The ogc_manual_waterlevels view: one row per public manual reading, with
    the reading's parameter columns and its well's site columns.

    Station columns:
        - id <- "m-" || observation.id
        - thing_id <- water_well_thing.id
        - name <- water_well_thing.name
        - thing_type <- water_well_thing.thing_type
        - longitude, latitude <- location.point
        - datetime <- observation.observation_datetime (the independent axis)
        - release_status <- "public" (only public readings of public wells)

    Parameter columns (core/pygeoapi.py, parameter_columns):
        - observation_parameter_name <- "groundwater level below ground surface"
        - observation_value <- observation.value - measuring_point_height
        - observation_unit <- "ft"
        - qualifier_parameter_name <- "groundwater level reason"
        - qualifier_value <- observation.groundwater level reason

    Site columns, repeated on every reading of the well and published on
    /locations:
        - ground_surface_elevation <- location.elevation
        - ground_surface_elevation_units <- "m"
        - vertical_datum <- "NAVD88"
        - well_depth <- water_well_thing.well_depth
        - well_depth_units <- "ft"
        - geologic_formation <- jsonb {code, description}: the well's
          formation_completion_code and its lexicon definition
        - alternate_ids <- jsonb list of {id, relation, organization}, one per
          public thing_id_link row of the well
    """
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        # The fixture's link is private; only public links may be published.
        session.execute(
            text("UPDATE thing_id_link SET release_status = 'public' WHERE id = :lid"),
            {"lid": thing_id_link.id},
        )
        session.commit()

        formation_description = session.execute(
            text("SELECT definition FROM lexicon_term WHERE term = :code"),
            {"code": water_well_thing.formation_completion_code},
        ).scalar_one()

        rows = (
            session.execute(
                text("SELECT * FROM ogc_manual_waterlevels WHERE thing_id = :tid"),
                {"tid": water_well_thing.id},
            )
            .mappings()
            .all()
        )

    assert len(rows) == 1
    row = rows[0]

    # ------------------------------------------------------------ station
    assert row["id"] == groundwater_level_observation.id
    assert row["thing_id"] == water_well_thing.id
    assert row["name"] == water_well_thing.name
    assert row["thing_type"] == water_well_thing.thing_type
    latitude, longitude = location.latlon
    assert row["longitude"] == pytest.approx(longitude)
    assert row["latitude"] == pytest.approx(latitude)
    assert row["datetime"] == datetime.fromisoformat(
        groundwater_level_observation.observation_datetime
    )
    assert row["release_status"] == "public"

    # ---------------------------------------------------------- parameters
    assert row["observation_parameter_name"] == "groundwater level below ground surface"
    assert row["observation_value"] == pytest.approx(
        groundwater_level_observation.value
        - groundwater_level_observation.measuring_point_height
    )
    assert row["observation_unit"] == "ft"
    assert row["qualifier_parameter_name"] == "groundwater level reason"
    assert (
        row["qualifier_value"] == groundwater_level_observation.groundwater_level_reason
    )

    # --------------------------------------------------------------- site
    assert row["ground_surface_elevation"] == pytest.approx(location.elevation)
    assert row["ground_surface_elevation_units"] == "m"
    assert row["vertical_datum"] == "NAVD88"
    assert row["well_depth"] == pytest.approx(water_well_thing.well_depth)
    assert row["well_depth_units"] == "ft"
    # jsonb columns come back as Python dicts and lists
    assert row["geologic_formation"] == {
        "code": water_well_thing.formation_completion_code,
        "description": formation_description,
    }
    assert row["alternate_ids"] == [
        {
            "id": thing_id_link.alternate_id,
            "relation": thing_id_link.relation,
            "organization": thing_id_link.alternate_organization,
        }
    ]


def test_ogc_manual_waterlevels_view_with_null_measuring_point(
    water_well_thing,
    groundwater_level_observation,
):
    """
    Test that the ogc_manual_waterlevels view correctly handles a null measuring point height by subtracting 0
    from the observation's value. This comes from docs/measuring-point-height-null-handling.md
    """
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

        # update the observation in the database to reflect the null measuring point height
        session.execute(
            text(
                "UPDATE observation SET measuring_point_height = NULL WHERE id = :oid"
            ),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()
        result = (
            session.execute(
                text("SELECT * FROM ogc_manual_waterlevels WHERE thing_id = :tid"),
                {"tid": water_well_thing.id},
            )
            .mappings()
            .all()
        )
        assert len(result) == 1
        row = result[0]

        assert row["observation_value"] == groundwater_level_observation.value - 0


@pytest.mark.parametrize(
    "unit,expected_value,expected_reason",
    [
        # feet as stored: 10 ft reading - 5 ft measuring point
        ("ft", 10.0 - 5.0, "Water level not affected"),
        # meters converted to feet before the (feet) measuring point is taken off
        ("m", 10.0 * 3.28084 - 5.0, "Water level not affected"),
        # any other unit: no level, and the reason says why
        ("dimensionless", None, "Reported unit is not a length unit"),
    ],
)
def test_ogc_manual_waterlevels_view_publishes_levels_in_feet(
    water_well_thing,
    groundwater_level_observation,
    unit,
    expected_value,
    expected_reason,
):
    """observation_value is always feet below ground surface.

    A reading in meters is converted to feet; measuring_point_height is always
    feet, so it is subtracted after the conversion. A reading in any other unit
    cannot be converted: its level is NULL, and qualifier_value records why in
    place of the recorded reason.
    """
    assert groundwater_level_observation.value == 10.0
    assert groundwater_level_observation.measuring_point_height == 5.0

    with session_ctx() as session:
        session.execute(
            text(
                "UPDATE observation SET release_status = 'public', unit = :unit "
                "WHERE id = :oid"
            ),
            {"unit": unit, "oid": groundwater_level_observation.id},
        )
        session.commit()

        rows = (
            session.execute(
                text("SELECT * FROM ogc_manual_waterlevels WHERE id = :oid"),
                {"oid": groundwater_level_observation.id},
            )
            .mappings()
            .all()
        )

    assert len(rows) == 1
    row = rows[0]
    assert row["observation_unit"] == "ft"
    if expected_value is None:
        assert row["observation_value"] is None
    else:
        assert row["observation_value"] == pytest.approx(expected_value)
    assert row["qualifier_value"] == expected_reason


def test_ogc_manual_waterlevels_view_handles_ftbgs_unit(
    water_well_thing,
    groundwater_level_observation,
):
    """Test that the view correctly handles the 'ftbgs' unit and does not subtract the measuring_point_height."""
    test_ogc_manual_waterlevels_view_publishes_levels_in_feet(
        water_well_thing,
        groundwater_level_observation,
        "ftbgs",
        10.0,
        "Water level not affected",
    )


@pytest.fixture()
def spring_groundwater_level_observation(spring_thing):
    """A public groundwater-level reading on a public spring.

    Everything the view's release and reading filters ask for is satisfied, so
    only its thing_type = 'water well' join condition can keep this row out.
    """
    with session_ctx() as session:
        # spring_thing is a draft; make it public so the release filter alone
        # cannot exclude it. spring_thing's teardown deletes the row.
        session.execute(
            text("UPDATE thing SET release_status = 'public' WHERE id = :tid"),
            {"tid": spring_thing.id},
        )
        field_event = FieldEvent(
            thing_id=spring_thing.id,
            event_date="2025-01-01T00:00:00Z",
            release_status="public",
        )
        session.add(field_event)
        session.flush()
        field_activity = FieldActivity(
            field_event_id=field_event.id,
            activity_type="groundwater level",
            release_status="public",
        )
        session.add(field_activity)
        session.flush()
        sample = Sample(
            field_activity_id=field_activity.id,
            sample_date="2025-01-01T12:00:00Z",
            sample_name="spring groundwater level sample",
            sample_matrix="water",
            sample_method="Steel-tape measurement",
            qc_type="Normal",
            release_status="public",
        )
        session.add(sample)
        session.flush()
        observation = Observation(
            observation_datetime="2025-01-01T00:04:00Z",
            sample_id=sample.id,
            parameter_id=get_parameter_id("groundwater level", "Field Parameter"),
            release_status="public",
            value=10.0,
            unit="ft",
            measuring_point_height=5.0,
            groundwater_level_reason="Water level not affected",
        )
        session.add(observation)
        session.commit()

        yield observation

        for row in (observation, sample, field_activity, field_event):
            session.delete(row)
            session.commit()


def test_ogc_manual_waterlevels_view_only_contains_water_wells(
    water_well_thing,
    spring_thing,
    groundwater_level_observation,
    spring_groundwater_level_observation,
):
    """
    The ogc_manual_waterlevels view only contains rows for water wells.

    The spring carries a public reading that passes every other filter in the
    view, so removing the thing_type = 'water well' condition fails this test.
    """
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

        # Guard: the spring must be public, or the release filter alone would
        # hide its reading and this test would not exercise the type filter.
        assert (
            session.execute(
                text(
                    "SELECT count(*) FROM thing WHERE id = :tid AND release_status = 'public'"
                ),
                {"tid": spring_thing.id},
            ).scalar_one()
            == 1
        )

        result = (
            session.execute(
                text(
                    "SELECT * FROM ogc_manual_waterlevels "
                    "WHERE thing_id IN (:well_id, :spring_id)"
                ),
                {"well_id": water_well_thing.id, "spring_id": spring_thing.id},
            )
            .mappings()
            .all()
        )

    assert [row["id"] for row in result] == [groundwater_level_observation.id]
    assert result[0]["thing_id"] == water_well_thing.id
    assert result[0]["thing_type"] == "water well"
    assert spring_groundwater_level_observation.id not in {row["id"] for row in result}
