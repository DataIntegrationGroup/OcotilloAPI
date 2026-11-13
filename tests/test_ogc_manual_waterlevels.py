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
  groundwater_level_reason terms, which the contract defers to.
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
from db.engine import session_ctx
from tests import override_authentication

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
    with session_ctx() as session:
        session.execute(
            text(
                f"UPDATE observation SET release_status = 'public' WHERE id = '{groundwater_level_observation.id}'"
            ),
        )
        session.execute(
            text(
                f"UPDATE thing SET release_status = 'draft' WHERE id = '{water_well_thing.id}'"
            ),
        )
        session.commit()

        public_rows = session.execute(
            text(
                f"SELECT id FROM ogc_manual_waterlevels WHERE id = '{water_well_thing.id}'"
            ),
        ).all()
        assert not public_rows, "a non-public well leaked a reading to /ogcapi"

        # The internal mount is where staff see non-public records; it must
        # keep carrying them.
        internal_rows = session.execute(
            text(
                f"SELECT id FROM ogc_internal_manual_waterlevels WHERE id = '{water_well_thing.id}'"
            ),
        ).all()
        assert internal_rows, "the internal mirror stopped carrying the reading"

        # Public well, public reading: published again.
        session.execute(
            text(
                f"UPDATE thing SET release_status = 'public' WHERE id = '{water_well_thing.id}'"
            ),
        )
        session.commit()

        assert session.execute(
            text(
                f"SELECT id FROM ogc_manual_waterlevels WHERE id = '{water_well_thing.id}'"
            ),
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
        "code": "100QBAS",
        "description": "Quaternary basalt",
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
        "Depth from the ground surface down to the water table, measured by hand "
        "during a site visit. Larger values mean the water table is further below "
        "the surface."
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
        "USGS-style condition codes explaining why a water level reads as it does "
        "or could not be measured."
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


# --------------------
# TEST VIEWS OGC_MANUAL_WATERLEVELS DEPEND ON
# --------------------


def test_ogc_manual_waterlevels_view(
    location,
    water_well_thing,
    groundwater_level_observation,
):
    """
    Test that the ogc_manual_waterlevels view has the intended structure and content.

    columns:
        - thing_id <- water_well_thing.id
        - station_name <- water_well_thing.name
        - longitude <- location.longitude
        - latitude <- location.latitude
        - datetime <- groundwater_level_observation.observation_datetime
        - observation_value <- groundwater_level_observation.value - groundwater_level_observation.measuring_point_height
        - observation_unit <- groundwater_level_observation.unit
        - observation_parameter_name <- "groundwater level below ground surface"
        - qualifier_value <- groundwater_level_observation.groundwater_level_reason
        - qualifier_parameter_name <- "groundwater level reason"

    The alternate ids will be pulled separately from the thing_id_link table.
    """
    with session_ctx() as session:
        session.execute(
            text("UPDATE observation SET release_status = 'public' WHERE id = :oid"),
            {"oid": groundwater_level_observation.id},
        )
        session.commit()

        result = session.execute(
            text(
                f"SELECT * FROM ogc_manual_waterlevels WHERE thing_id = '{water_well_thing.id}'"
            )
        ).fetchall()
        assert len(result) == 1
        row = result[0]

        assert row["thing_id"] == water_well_thing.id
        assert row["station_name"] == water_well_thing.name
        lat, lon = location.latlon
        assert row["longitude"] == lon
        assert row["latitude"] == lat
        assert row["datetime"] == groundwater_level_observation.observation_datetime
        assert (
            row["observation_value"]
            == groundwater_level_observation.value
            - groundwater_level_observation.measuring_point_height
        )
        assert row["observation_unit"] == groundwater_level_observation.unit
        assert (
            row["observation_parameter_name"]
            == "groundwater level below ground surface"
        )
        assert (
            row["qualifier_value"]
            == groundwater_level_observation.groundwater_level_reason
        )
        assert row["qualifier_parameter_name"] == "groundwater level reason"


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
                f"UPDATE observation SET measuring_point_height = NULL WHERE id = '{groundwater_level_observation.id}'"
            )
        )
        session.commit()
        result = session.execute(
            text(
                f"SELECT * FROM ogc_manual_waterlevels WHERE thing_id = '{water_well_thing.id}'"
            )
        ).fetchall()
        assert len(result) == 1
        row = result[0]

        assert row["observation_value"] == groundwater_level_observation.value - 0
