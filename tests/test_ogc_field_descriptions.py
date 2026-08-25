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
"""Field-level documentation on /schema and /queryables, both mounts.

`geometry` is excluded from the "every property is documented" assertions
throughout: pygeoapi injects it itself, after the provider's fields, with only
a format and an x-ogc-role.
"""

import pytest
from fastapi.testclient import TestClient

from core.factory import create_api_app
from core.dependencies import (
    admin_function,
    amp_admin_function,
    amp_editor_function,
    amp_viewer_function,
    editor_function,
    viewer_function,
)
from core.ogc_field_metadata import table_entries
from tests import override_authentication

GEOMETRY_PROPERTY = "geometry"


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


def _documented_properties(payload):
    return {
        name: prop
        for name, prop in payload["properties"].items()
        if name != GEOMETRY_PROPERTY
    }


# --------------------------------------------------------------------- schema


def test_schema_documents_every_property(ogc_client):
    response = ogc_client.get("/ogcapi/collections/water_wells/schema")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/schema+json")
    for name, prop in _documented_properties(response.json()).items():
        assert prop.get("title"), f"{name} has no title"


def test_schema_carries_the_authored_prose(ogc_client):
    properties = ogc_client.get("/ogcapi/collections/water_wells/schema").json()[
        "properties"
    ]

    assert properties["well_depth"]["title"] == "Well depth"
    assert properties["well_depth"]["description"].startswith(
        "Total depth of the finished well"
    )
    assert properties["well_depth"]["x-ogc-unit"] == "https://qudt.org/vocab/unit/FT"
    assert properties["well_depth"]["x-ogc-unitLang"] == "QUDT"
    assert properties["nma_formation_zone"]["title"] == "Legacy formation zone"


def test_schema_keeps_pygeoapi_roles(ogc_client):
    # The annotation must not displace the roles pygeoapi assigns after the
    # provider hands its fields over.
    properties = ogc_client.get("/ogcapi/collections/water_wells/schema").json()[
        "properties"
    ]

    assert properties["id"]["x-ogc-role"] == "id"
    assert properties[GEOMETRY_PROPERTY]["x-ogc-role"] == "primary-geometry"
    assert properties["first_visit_date"]["x-ogc-role"] == "primary-instant"


def test_schema_roles_do_not_leak_between_requests(ogc_client):
    # describe_fields hands out fresh dicts precisely so that pygeoapi's
    # in-place mutation of one response cannot reach the next one.
    first = ogc_client.get("/ogcapi/collections/water_wells/schema").json()
    second = ogc_client.get("/ogcapi/collections/water_wells/schema").json()

    assert first["properties"] == second["properties"]
    assert "x-ogc-role" not in second["properties"]["well_depth"]


def test_derived_collections_document_their_calculated_columns(ogc_client):
    properties = ogc_client.get(
        "/ogcapi/collections/depth_to_water_trend_wells/schema"
    ).json()["properties"]

    assert properties["slope_ft_per_year"]["title"] == "Trend slope"
    assert "water table is falling" in properties["slope_ft_per_year"]["description"]
    assert properties["trend_category"]["description"].startswith(
        "Plain-language reading of the slope"
    )


def test_chemistry_analyte_columns_are_documented(ogc_client):
    properties = ogc_client.get(
        "/ogcapi/collections/major_chemistry_results/schema"
    ).json()["properties"]

    assert properties["tds"]["title"] == "Total dissolved solids"
    assert properties["tds_units"]["title"] == "Total dissolved solids units"
    assert properties["ion_balance"]["description"].startswith("Percentage difference")


# ---------------------------------------------------------------- both mounts


@pytest.mark.parametrize("mount", ["/ogcapi", "/ogcapi-internal"])
@pytest.mark.parametrize("endpoint", ["schema", "queryables"])
def test_both_mounts_document_water_wells(ogc_client, mount, endpoint):
    response = ogc_client.get(f"{mount}/collections/water_wells/{endpoint}")

    assert response.status_code == 200
    properties = _documented_properties(response.json())
    assert properties["well_depth"]["title"] == "Well depth"
    for name, prop in properties.items():
        assert prop.get("title"), f"{mount} {endpoint}: {name} has no title"


def test_internal_only_collection_is_documented(ogc_client):
    # other_things is published on the internal mount only (BDMS-979); its
    # backing view is ogc_internal_other_things, so the "ogc_internal_"
    # prefix has to be stripped for the lookup to land.
    response = ogc_client.get("/ogcapi-internal/collections/other_things/schema")

    assert response.status_code == 200
    properties = _documented_properties(response.json())
    assert properties["well_depth"]["title"] == "Well depth"
    assert properties["release_status"]["description"]


# ----------------------------------------------------------------- rendering


@pytest.mark.parametrize("endpoint", ["schema", "queryables"])
@pytest.mark.parametrize("fmt", ["json", "html"])
def test_endpoints_render_in_both_formats(ogc_client, endpoint, fmt):
    response = ogc_client.get(
        f"/ogcapi/collections/water_wells/{endpoint}", params={"f": fmt}
    )

    assert response.status_code == 200


# --------------------------------------------------------------- drift guard


def _feature_collection_tables(client, mount):
    payload = client.get(f"{mount}/collections").json()
    return [collection["id"] for collection in payload["collections"]]


def test_every_published_column_has_an_entry(ogc_client):
    """A renamed or added matview column must fail here, not degrade the API.

    EDR collections are excluded on purpose: their fields are analyte names
    read out of the data, not the backing view's columns.
    """
    undocumented = {}

    for mount in ("/ogcapi", "/ogcapi-internal"):
        for collection_id in _feature_collection_tables(ogc_client, mount):
            response = ogc_client.get(f"{mount}/collections/{collection_id}/schema")
            if response.status_code != 200:
                continue
            payload = response.json()
            if payload.get("type") != "object":
                continue
            gaps = [
                name
                for name, prop in _documented_properties(payload).items()
                if not prop.get("description")
            ]
            if gaps:
                undocumented[f"{mount}/{collection_id}"] = sorted(gaps)

    assert not undocumented, f"columns with no YAML entry: {undocumented}"


def test_fallback_title_for_an_undocumented_column():
    # The fallback path itself, without needing a real undocumented column in
    # the database.
    from core.ogc_field_metadata import describe_fields

    described = describe_fields(
        "ogc_water_wells", {"brand_new_column": {"type": "string"}}
    )

    assert described["brand_new_column"]["title"] == "Brand New Column"
    assert "description" not in described["brand_new_column"]


def test_defaults_cover_the_shared_thing_columns():
    # All 11 thing-type views share one column signature, so a gap in
    # _defaults would hit every one of them at once.
    entries = table_entries("ogc_springs")

    for column in (
        "id",
        "name",
        "first_visit_date",
        "well_depth",
        "release_status",
        "elevation",
    ):
        assert entries[column]["description"], f"{column} lost its default entry"


# ------------------------------------------------------------- upgrade guard


def test_pygeoapi_still_passes_provider_fields_through_to_schema():
    """Guard on the pygeoapi behaviour this whole feature rests on.

    `get_collection_schema` copies each provider field entry into the response
    wholesale, which is why documentation set by the provider reaches the
    client. A pygeoapi bump that rebuilds the dict instead -- the way
    `get_collection_queryables` already does -- would silently drop every
    description. Fail loudly here instead.
    """
    import inspect

    from pygeoapi.api import get_collection_schema

    source = inspect.getsource(get_collection_schema)

    assert "schema['properties'][k] = v" in source, (
        "pygeoapi no longer assigns the provider's field entry into the schema "
        "response; /schema descriptions need re-checking against the new "
        "implementation (see docs/ogc-field-descriptions.md)."
    )


# ----------------------------------------------------------------------- EDR


def test_edr_schema_documents_its_parameter(ogc_client):
    response = ogc_client.get("/ogcapi/collections/waterlevels/schema")

    assert response.status_code == 200
    properties = response.json()["properties"]
    if "groundwater level" not in properties:
        # EDR fields are read out of the data, not reflected from columns, so
        # this assertion only has something to bite on when the suite has left
        # water-level rows behind. The CoverageJSON test below covers the same
        # lookup without needing any.
        pytest.skip("no water-level rows in ogc_waterlevels for this database state")
    parameter = properties["groundwater level"]
    assert parameter["title"] == "Groundwater level"
    assert parameter["description"].startswith("Depth from the measuring point")


def test_edr_coveragejson_carries_the_parameter_description():
    # Exercises the CoverageJSON parameters block without a database: the
    # provider's __init__ opens a connection, which this does not need.
    from datetime import datetime

    from core.edr_provider import WaterEDRProvider

    provider = object.__new__(WaterEDRProvider)
    provider.table = "ogc_waterlevels"

    coverage = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "station_name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 1),
                "value": 42.0,
                "unit": "ft",
                "parameter_name": "groundwater level",
            }
        ]
    )

    parameter = coverage["parameters"]["groundwater level"]
    assert parameter["observedProperty"]["label"]["en"] == "Groundwater level"
    assert parameter["description"]["en"].startswith("Depth from the measuring point")


def test_edr_falls_back_for_an_undocumented_analyte():
    from datetime import datetime

    from core.edr_provider import WaterEDRProvider

    provider = object.__new__(WaterEDRProvider)
    provider.table = "ogc_water_chemistry"

    coverage = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "station_name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 1),
                "value": 1.0,
                "unit": "mg/L",
                "parameter_name": "Some Unmapped Analyte",
            }
        ]
    )

    parameter = coverage["parameters"]["Some Unmapped Analyte"]
    assert parameter["observedProperty"]["label"]["en"] == "Some Unmapped Analyte"
    assert parameter["description"]["en"] == "Some Unmapped Analyte"


# ---------------------------------------------------------- enumerated values


def test_schema_publishes_enumerated_values(ogc_client):
    # pygeoapi's HTML schema view renders `enum` as its "Values" column, and
    # nothing fills it in: the SQL provider reports only type and format, and
    # implements no get_domains(). These come from the YAML.
    properties = ogc_client.get(
        "/ogcapi/collections/depth_to_water_trend_wells/schema"
    ).json()["properties"]

    assert properties["trend_category"]["enum"] == [
        "increasing",
        "decreasing",
        "stable",
        "not enough data",
    ]


def test_queryables_publishes_enumerated_values(ogc_client):
    properties = ogc_client.get(
        "/ogcapi/collections/depth_to_water_trend_wells/queryables"
    ).json()["properties"]

    assert "not enough data" in properties["trend_category"]["enum"]


def test_lexicon_backed_enums_come_from_the_lexicon(ogc_client):
    from core.ogc_field_metadata import lexicon_terms

    properties = ogc_client.get("/ogcapi/collections/water_wells/schema").json()[
        "properties"
    ]

    assert properties["well_pump_type"]["enum"] == lexicon_terms("well_pump_type")
    assert properties["well_construction_method"]["enum"] == lexicon_terms(
        "well_construction_method"
    )
    assert properties["release_status"]["enum"] == lexicon_terms("release_status")


def test_enum_lexicon_key_is_expanded_not_published(ogc_client):
    # The YAML shorthand must not reach the client.
    properties = ogc_client.get("/ogcapi/collections/water_wells/schema").json()[
        "properties"
    ]

    assert "enum-lexicon" not in properties["well_pump_type"]


def test_enum_entries_validate_against_the_lexicon():
    # A category with no terms is a typo, and it must fail at load rather than
    # publish an empty Values column.
    import pytest as _pytest

    from core.ogc_field_metadata import _validate

    with _pytest.raises(ValueError, match="no terms"):
        _validate(
            {"water_wells": {"well_pump_type": {"title": "x", "enum-lexicon": "nope"}}},
            "test.yml",
        )

    with _pytest.raises(ValueError, match="non-empty list"):
        _validate({"water_wells": {"a_column": {"title": "x", "enum": []}}}, "test.yml")
