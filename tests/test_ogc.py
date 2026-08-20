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
from datetime import date, datetime
from importlib.util import find_spec
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from core.dependencies import (
    admin_function,
    editor_function,
    amp_admin_function,
    amp_editor_function,
    viewer_function,
    amp_viewer_function,
)
from core.factory import create_api_app
from db import (
    Group,
    GroupThingAssociation,
    NMA_Chemistry_SampleInfo,
    NMA_MajorChemistry,
    NMA_MinorTraceChemistry,
    StatusHistory,
)
from db.engine import session_ctx
from tests import override_authentication

pytestmark = pytest.mark.skipif(
    find_spec("pygeoapi") is None,
    reason="pygeoapi is not installed in this environment",
)


@pytest.fixture(scope="module", autouse=True)
def ogc_client():
    app = create_api_app()
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

    with TestClient(app) as client:
        yield client

    app.dependency_overrides = {}


def test_ogc_landing(ogc_client):
    response = ogc_client.get("/ogcapi")
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"]
    assert any(link["rel"] == "self" for link in payload["links"])


def test_ogc_conformance(ogc_client):
    response = ogc_client.get("/ogcapi/conformance")
    assert response.status_code == 200
    payload = response.json()
    assert "conformsTo" in payload
    assert any("ogcapi-features" in item for item in payload["conformsTo"])


def test_ogc_openapi_has_paths(ogc_client):
    response = ogc_client.get("/ogcapi/openapi?f=json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openapi"].startswith("3.")
    assert payload["paths"]
    assert "/collections" in payload["paths"]


# A2: every surface that echoes metadata from core/pygeoapi-config.yml.
# The JSON landing page carries only title/description/links, so the
# provider/contact/terms assertions below have to go through the OpenAPI
# document -- see pygeoapi.api.landing_page vs pygeoapi.openapi.get_oas_30.
@pytest.mark.parametrize(
    "path,params",
    [
        ("/ogcapi", {"f": "json"}),
        ("/ogcapi", {"f": "html"}),
        ("/ogcapi/openapi", {}),
        ("/ogcapi/collections", {"f": "json"}),
    ],
)
def test_ogc_metadata_has_no_placeholders(ogc_client, path, params):
    response = ogc_client.get(path, params=params)
    assert response.status_code == 200
    assert "example.com" not in response.text


def test_ogc_openapi_contact_metadata(ogc_client):
    response = ogc_client.get("/ogcapi/openapi?f=json")
    assert response.status_code == 200
    info = response.json()["info"]

    # info.contact is built from metadata.provider, and metadata.contact is
    # nested under the x-ogc-serviceContact extension.
    assert info["contact"]["name"] == "NMBGMR"
    assert info["contact"]["url"] == "https://geoinfo.nmt.edu"
    assert info["contact"]["email"] == "ocotillo-nmbg@nmt.edu"

    service_contact = info["contact"]["x-ogc-serviceContact"]
    assert service_contact["name"] == "Ocotillo Support, NMBGMR"
    assert service_contact["emails"][0]["value"] == "ocotillo-nmbg@nmt.edu"


def test_ogc_terms_of_service_resolves(ogc_client):
    response = ogc_client.get("/ogcapi/openapi?f=json")
    terms_url = response.json()["info"]["termsOfService"]
    parsed = urlparse(terms_url)
    assert parsed.scheme in ("http", "https")
    assert parsed.path == "/disclaimer"

    # An advertised terms_of_service that 404s is no better than a placeholder.
    disclaimer = ogc_client.get(parsed.path)
    assert disclaimer.status_code == 200
    assert "New Mexico Bureau of Geology and Mineral Resources" in disclaimer.text


def test_ogc_landing_page_advertises_service_url(ogc_client):
    response = ogc_client.get("/ogcapi", params={"f": "json"})
    about = [link for link in response.json()["links"] if link["rel"] == "about"]
    assert about, "landing page has no rel=about link"
    assert about[0]["href"] == "https://ocotillo.newmexicowaterdata.org"


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


def test_ogc_major_chemistry_results_uses_latest_per_analyte(water_well_thing):
    with session_ctx() as session:
        csi = NMA_Chemistry_SampleInfo(
            thing_id=water_well_thing.id,
            nma_sample_point_id="MAJNORM01",
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

        session.execute(text("REFRESH MATERIALIZED VIEW ogc_major_chemistry_results"))
        session.commit()

        row = session.execute(
            text(
                "SELECT calcium, calcium_units, chloride, chloride_units, latest_chemistry_date "
                "FROM ogc_major_chemistry_results WHERE id = :thing_id"
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
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_major_chemistry_results"))
        session.commit()


def test_ogc_minor_chemistry_wells_uses_latest_per_analyte(water_well_thing):
    with session_ctx() as session:
        csi = NMA_Chemistry_SampleInfo(
            thing_id=water_well_thing.id,
            nma_sample_point_id="MINRNORM1",
            collection_date=datetime(2024, 4, 1, 10, 0, 0),
        )
        session.add(csi)
        session.flush()

        # Older barium result
        barium_old = NMA_MinorTraceChemistry(
            chemistry_sample_info_id=csi.id,
            nma_sample_point_id="MINRNORM1",
            analyte="Ba",
            symbol="",
            sample_value=0.40,
            units="mg/L",
            analysis_date=date(2024, 4, 1),
        )
        # Newer barium result that should win for barium + barium_units
        barium_new = NMA_MinorTraceChemistry(
            chemistry_sample_info_id=csi.id,
            nma_sample_point_id="MINRNORM1",
            analyte="Ba",
            symbol="",
            sample_value=0.55,
            units="ug/L",
            analysis_date=date(2024, 4, 2),
        )
        # Separate analyte with even later date to drive latest_chemistry_date
        fluoride = NMA_MinorTraceChemistry(
            chemistry_sample_info_id=csi.id,
            nma_sample_point_id="MINRNORM1",
            analyte="F",
            symbol="",
            sample_value=1.2,
            units="mg/L",
            analysis_date=date(2024, 4, 3),
        )

        session.add_all([barium_old, barium_new, fluoride])
        session.commit()

        session.execute(text("REFRESH MATERIALIZED VIEW ogc_minor_chemistry_wells"))
        session.commit()

        row = session.execute(
            text(
                "SELECT barium, barium_units, fluoride, fluoride_units, latest_chemistry_date "
                "FROM ogc_minor_chemistry_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert float(row.barium) == 0.55
        assert row.barium_units == "ug/L"
        assert float(row.fluoride) == 1.2
        assert row.fluoride_units == "mg/L"
        assert row.latest_chemistry_date.isoformat() == "2024-04-03"

        session.delete(fluoride)
        session.delete(barium_new)
        session.delete(barium_old)
        session.delete(csi)
        session.commit()
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_minor_chemistry_wells"))
        session.commit()


def test_ogc_water_elevation_wells_computes_elevation_minus_depth_to_water(
    water_well_thing, groundwater_level_observation
):
    with session_ctx() as session:
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_elevation_wells"))
        session.commit()

        row = session.execute(
            text(
                "SELECT elevation_m, depth_to_water_below_ground_surface_ft, water_elevation_ft "
                "FROM ogc_water_elevation_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert float(row.depth_to_water_below_ground_surface_ft) == 5.0
        assert float(row.elevation_m) == 2464.9
        expected_water_elevation_ft = (2464.9 * 3.28084) - 5.0
        assert abs(float(row.water_elevation_ft) - expected_water_elevation_ft) < 1e-9


def test_ogc_water_elevation_wells_normalizes_meter_observations_to_feet(
    water_well_thing, groundwater_level_observation
):
    with session_ctx() as session:
        meter_observation = groundwater_level_observation.__class__(
            observation_datetime=datetime(2025, 1, 2, 0, 4, 0),
            sample_id=groundwater_level_observation.sample_id,
            sensor_id=groundwater_level_observation.sensor_id,
            parameter_id=groundwater_level_observation.parameter_id,
            release_status="draft",
            value=3.0,
            unit="m",
            measuring_point_height=2.0,
            groundwater_level_reason="Water level not affected",
        )
        session.add(meter_observation)
        session.commit()

        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_elevation_wells"))
        session.commit()

        row = session.execute(
            text(
                "SELECT depth_to_water_below_ground_surface_ft, water_elevation_ft "
                "FROM ogc_water_elevation_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        expected_depth_ft = (3.0 * 3.28084) - 2.0
        expected_water_elevation_ft = (2464.9 * 3.28084) - expected_depth_ft

        assert (
            abs(float(row.depth_to_water_below_ground_surface_ft) - expected_depth_ft)
            < 1e-9
        )
        assert abs(float(row.water_elevation_ft) - expected_water_elevation_ft) < 1e-9

        session.delete(meter_observation)
        session.commit()
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_elevation_wells"))
        session.commit()


def test_ogc_actively_monitored_wells_exposes_water_level_network_group_wells(
    water_well_thing,
    groundwater_level_observation,
):
    with session_ctx() as session:
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_well_summary"))
        session.commit()

        group = Group(
            name="Water Level Network",
            group_type="Monitoring Plan",
            release_status="public",
        )
        session.add(group)
        session.flush()

        group_assoc = GroupThingAssociation(
            group_id=group.id,
            thing_id=water_well_thing.id,
        )
        session.add(group_assoc)
        status_history = StatusHistory(
            status_type="Monitoring Status",
            status_value="Currently monitored",
            start_date=date(2024, 1, 1),
            target_id=water_well_thing.id,
            target_table="thing",
        )
        session.add(status_history)
        session.commit()

        row = session.execute(
            text(
                "SELECT group_id, group_name, group_type "
                "FROM ogc_actively_monitored_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert row.group_id == group.id
        assert row.group_name == "Water Level Network"
        assert row.group_type == "Monitoring Plan"

        session.delete(status_history)
        session.delete(group_assoc)
        session.delete(group)
        session.commit()


def test_ogc_actively_monitored_wells_excludes_latest_not_currently_monitored(
    water_well_thing,
    groundwater_level_observation,
):
    with session_ctx() as session:
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_well_summary"))
        session.commit()

        group = Group(
            name="Water Level Network",
            group_type="Monitoring Plan",
            release_status="public",
        )
        session.add(group)
        session.flush()

        group_assoc = GroupThingAssociation(
            group_id=group.id,
            thing_id=water_well_thing.id,
        )
        session.add(group_assoc)
        currently_monitored = StatusHistory(
            status_type="Monitoring Status",
            status_value="Currently monitored",
            start_date=date(2024, 1, 1),
            target_id=water_well_thing.id,
            target_table="thing",
        )
        not_currently_monitored = StatusHistory(
            status_type="Monitoring Status",
            status_value="Not currently monitored",
            start_date=date(2024, 2, 1),
            target_id=water_well_thing.id,
            target_table="thing",
        )
        session.add_all([currently_monitored, not_currently_monitored])
        session.commit()

        row = session.execute(
            text("SELECT id FROM ogc_actively_monitored_wells WHERE id = :thing_id"),
            {"thing_id": water_well_thing.id},
        ).one_or_none()

        assert row is None

        session.delete(not_currently_monitored)
        session.delete(currently_monitored)
        session.delete(group_assoc)
        session.delete(group)
        session.commit()


def test_ogc_actively_monitored_wells_includes_wells_from_other_groups(
    water_well_thing,
    groundwater_level_observation,
):
    with session_ctx() as session:
        session.execute(text("REFRESH MATERIALIZED VIEW ogc_water_well_summary"))
        session.commit()

        group = Group(
            name="Test Other Group",
            group_type="Monitoring Plan",
            release_status="public",
        )
        session.add(group)
        session.flush()

        group_assoc = GroupThingAssociation(
            group_id=group.id,
            thing_id=water_well_thing.id,
        )
        session.add(group_assoc)
        status_history = StatusHistory(
            status_type="Monitoring Status",
            status_value="Currently monitored",
            start_date=date(2024, 1, 1),
            target_id=water_well_thing.id,
            target_table="thing",
        )
        session.add(status_history)
        session.commit()

        row = session.execute(
            text(
                "SELECT group_id, group_name, group_type "
                "FROM ogc_actively_monitored_wells WHERE id = :thing_id"
            ),
            {"thing_id": water_well_thing.id},
        ).one()

        assert row.group_id == group.id
        assert row.group_name == "Test Other Group"
        assert row.group_type == "Monitoring Plan"

        session.delete(status_history)
        session.delete(group_assoc)
        session.delete(group)
        session.commit()


def test_ogc_collections(ogc_client):
    response = ogc_client.get("/ogcapi/collections")
    assert response.status_code == 200
    payload = response.json()
    ids = {collection["id"] for collection in payload["collections"]}
    assert {
        "water_wells",
        "springs",
        "latest_tds_wells",
        "depth_to_water_trend_wells",
        "water_elevation_wells",
        "water_well_summary",
        "major_chemistry_results",
        "minor_chemistry_wells",
        "actively_monitored_wells",
        "project_areas",
    }.issubset(ids)
    # Hidden from the public catalog: locations duplicates the thing-type
    # layers (BDMS-978), avg_tds_wells averages ~1.9 observations per well
    # and latest_depth_to_water_wells repeats water_well_summary
    # (BDMS-977), and other_things is internal vocabulary (BDMS-979). The
    # backing relations are retained and still served on /ogcapi-internal.
    assert ids.isdisjoint(
        {
            "locations",
            "avg_tds_wells",
            "latest_depth_to_water_wells",
            "other_things",
        }
    )


def test_ogc_new_collection_items_endpoints(ogc_client):
    for collection_id in (
        "latest_tds_wells",
        "depth_to_water_trend_wells",
        "water_elevation_wells",
        "water_well_summary",
        "major_chemistry_results",
        "minor_chemistry_wells",
        "actively_monitored_wells",
        "project_areas",
    ):
        response = ogc_client.get(f"/ogcapi/collections/{collection_id}/items?limit=10")
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "FeatureCollection"


def test_ogc_project_areas_items_expose_groups_with_project_areas(ogc_client, group):
    response = ogc_client.get("/ogcapi/collections/project_areas/items?limit=20")

    assert response.status_code == 200
    payload = response.json()
    ids = {str(feature["id"]) for feature in payload["features"]}
    assert str(group.id) in ids


def test_ogc_wells_items_and_item(ogc_client, water_well_thing):
    response = ogc_client.get("/ogcapi/collections/water_wells/items?limit=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
    ids = {str(feature["id"]) for feature in payload["features"]}
    assert str(water_well_thing.id) in ids

    response = ogc_client.get(
        f"/ogcapi/collections/water_wells/items/{water_well_thing.id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert str(payload["id"]) == str(water_well_thing.id)


@pytest.mark.skip("PostGIS spatial operators not available in CI - see issue #449")
def test_ogc_polygon_within_filter(location):
    polygon = "POLYGON((-107.95 33.80,-107.94 33.80,-107.94 33.81,-107.95 33.81,-107.95 33.80))"
    response = ogc_client.get(
        "/ogcapi/collections/locations/items",
        params={
            "filter": f"WITHIN(geometry,{polygon})",
            "filter-lang": "cql2-text",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["numberReturned"] >= 1
