# ===============================================================================
# Copyright 2026
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
from datetime import datetime
from importlib.util import find_spec

import pytest
from sqlalchemy import text

from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)
from db import NMA_Chemistry_SampleInfo, NMA_MajorChemistry
from db.engine import session_ctx
from main import app
from tests import client, override_authentication

pytestmark = pytest.mark.skipif(
    find_spec("pygeoapi") is None,
    reason="pygeoapi is not installed in this environment",
)


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


def test_ogc_landing():
    response = client.get("/ogcapi")
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"]
    assert any(link["rel"] == "self" for link in payload["links"])


def test_ogc_conformance():
    response = client.get("/ogcapi/conformance")
    assert response.status_code == 200
    payload = response.json()
    assert "conformsTo" in payload
    assert any("ogcapi-features" in item for item in payload["conformsTo"])


def test_ogc_openapi_has_paths():
    response = client.get("/ogcapi/openapi?f=json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openapi"].startswith("3.")
    assert payload["paths"]
    assert "/collections" in payload["paths"]


def test_latest_tds_observation_date_falls_back_to_collection_date(water_well_thing):
    with session_ctx() as session:
        csi = NMA_Chemistry_SampleInfo(
            thing_id=water_well_thing.id,
            nma_sample_point_id="TDS-FALLBK",
            collection_date=datetime(2024, 1, 15, 12, 30, 0),
        )
        session.add(csi)
        session.flush()

        mc = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Total Dissolved Solids",
            symbol="TDS",
            sample_value=500.0,
            units="mg/L",
            analysis_date=None,
        )
        session.add(mc)
        session.commit()

        session.execute(text("REFRESH MATERIALIZED VIEW ogc_avg_tds_wells"))
        session.commit()

        latest_dt = session.execute(
            text(
                "SELECT latest_tds_observation_date "
                "FROM ogc_latest_tds_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).scalar_one()
        avg_range = session.execute(
            text(
                "SELECT first_tds_observation_date, last_tds_observation_date "
                "FROM ogc_avg_tds_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert latest_dt is not None
        assert latest_dt.isoformat() == "2024-01-15"
        assert avg_range.first_tds_observation_date is not None
        assert avg_range.last_tds_observation_date is not None
        assert avg_range.first_tds_observation_date.isoformat() == "2024-01-15"
        assert avg_range.last_tds_observation_date.isoformat() == "2024-01-15"

        session.delete(mc)
        session.delete(csi)
        session.commit()
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_avg_tds_wells"))
        session.commit()


def test_latest_tds_uses_latest_timestamp_within_same_day(water_well_thing):
    with session_ctx() as session:
        csi = NMA_Chemistry_SampleInfo(
            thing_id=water_well_thing.id,
            nma_sample_point_id="TDS-TIME",
            collection_date=datetime(2024, 2, 1, 9, 0, 0),
        )
        session.add(csi)
        session.flush()

        mc_early = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Total Dissolved Solids",
            symbol="TDS",
            sample_value=300.0,
            units="mg/L",
            analysis_date=datetime(2024, 2, 1, 8, 0, 0),
        )
        mc_late = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Total Dissolved Solids",
            symbol="TDS",
            sample_value=700.0,
            units="mg/L",
            analysis_date=datetime(2024, 2, 1, 18, 0, 0),
        )
        session.add(mc_early)
        session.add(mc_late)
        session.commit()

        session.execute(text("REFRESH MATERIALIZED VIEW ogc_avg_tds_wells"))
        session.commit()

        row = session.execute(
            text(
                "SELECT latest_tds_observation_date, latest_tds_value "
                "FROM ogc_latest_tds_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert row.latest_tds_observation_date.isoformat() == "2024-02-01"
        assert float(row.latest_tds_value) == 700.0

        session.delete(mc_late)
        session.delete(mc_early)
        session.delete(csi)
        session.commit()
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_avg_tds_wells"))
        session.commit()


def test_ogc_normalized_major_chemistry_uses_latest_per_analyte(water_well_thing):
    with session_ctx() as session:
        csi = NMA_Chemistry_SampleInfo(
            thing_id=water_well_thing.id,
            nma_sample_point_id="MAJOR-NORM-01",
            collection_date=datetime(2024, 3, 1, 10, 0, 0),
        )
        session.add(csi)
        session.flush()

        # Older calcium result
        calcium_old = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Ca",
            symbol="",
            sample_value=80.0,
            units="mg/L",
            analysis_date=datetime(2024, 3, 1, 9, 0, 0),
        )
        # Newer calcium result that should win for calcium + calcium_units
        calcium_new = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Ca",
            symbol="",
            sample_value=95.0,
            units="mg/L as CaCO3",
            analysis_date=datetime(2024, 3, 2, 9, 0, 0),
        )
        # Separate analyte with even later date to drive latest_chemistry_date
        chloride = NMA_MajorChemistry(
            chemistry_sample_info_id=csi.id,
            analyte="Cl",
            symbol="",
            sample_value=40.0,
            units="mg/L",
            analysis_date=datetime(2024, 3, 3, 8, 0, 0),
        )

        session.add_all([calcium_old, calcium_new, chloride])
        session.commit()

        session.execute(
            text("REFRESH MATERIALIZED VIEW ogc_normalized_chemistry_results")
        )
        session.commit()

        row = session.execute(
            text(
                "SELECT calcium, calcium_units, chloride, chloride_units, latest_chemistry_date "
                "FROM ogc_normalized_chemistry_results WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert float(row.calcium) == 95.0
        assert row.calcium_units == "mg/L as CaCO3"
        assert float(row.chloride) == 40.0
        assert row.chloride_units == "mg/L"
        assert row.latest_chemistry_date.isoformat() == "2024-03-03"

        session.delete(chloride)
        session.delete(calcium_new)
        session.delete(calcium_old)
        session.delete(csi)
        session.commit()
        session.execute(
            text("REFRESH MATERIALIZED VIEW ogc_normalized_chemistry_results")
        )
        session.commit()


def test_ogc_collections():
    response = client.get("/ogcapi/collections")
    assert response.status_code == 200
    payload = response.json()
    ids = {collection["id"] for collection in payload["collections"]}
    assert {
        "locations",
        "water_wells",
        "springs",
        "latest_tds_wells",
        "depth_to_water_trend_wells",
        "water_well_summary",
        "normalized_chemistry_results",
        "minor_chemistry_wells",
    }.issubset(ids)


def test_ogc_new_collection_items_endpoints():
    for collection_id in (
        "latest_tds_wells",
        "depth_to_water_trend_wells",
        "water_well_summary",
        "normalized_chemistry_results",
        "minor_chemistry_wells",
    ):
        response = client.get(f"/ogcapi/collections/{collection_id}/items?limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "FeatureCollection"


@pytest.mark.skip("PostGIS spatial operators not available in CI - see issue #449")
def test_ogc_locations_items_bbox(location):
    bbox = "-107.95,33.80,-107.94,33.81"
    response = client.get(f"/ogcapi/collections/locations/items?bbox={bbox}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["numberReturned"] >= 1


def test_ogc_wells_items_and_item(water_well_thing):
    response = client.get("/ogcapi/collections/water_wells/items?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
    ids = {str(feature["id"]) for feature in payload["features"]}
    assert str(water_well_thing.id) in ids

    response = client.get(
        f"/ogcapi/collections/water_wells/items/{water_well_thing.id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert str(payload["id"]) == str(water_well_thing.id)


@pytest.mark.skip("PostGIS spatial operators not available in CI - see issue #449")
def test_ogc_polygon_within_filter(location):
    polygon = "POLYGON((-107.95 33.80,-107.94 33.80,-107.94 33.81,-107.95 33.81,-107.95 33.80))"
    response = client.get(
        "/ogcapi/collections/locations/items",
        params={
            "filter": f"WITHIN(geometry,{polygon})",
            "filter-lang": "cql2-text",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
