"""Unit tests for the EDR provider, without a database.

Station metadata on /locations comes from each collection's station_properties
config: the listed view columns are published as GeoJSON properties under
their own names.
"""

from datetime import datetime
import logging
import textwrap
import pytest
import yaml

from core.edr_provider import StationEDRProvider, categories_from_lexicon
from core.pygeoapi import (
    EDR_COLLECTIONS,
    EDR_PROVIDER_COLLECTION_KEYS,
    _document_locations_parameter_name,
    _edr_collections_block,
    _is_parameter_name,
)


def _provider(station_properties=("name", "thing_type")) -> StationEDRProvider:
    # Bypass __init__: it connects to Postgres to read fields, which is not
    # what these tests are about.
    provider = object.__new__(StationEDRProvider)
    provider.station_properties = list(station_properties)
    return provider


def test_station_properties_publish_the_configured_columns_by_name():
    properties = _provider()._station_properties(
        {"name": "NM-28368", "thing_type": "spring"}
    )

    assert properties == {"name": "NM-28368", "thing_type": "spring"}


def test_station_properties_publish_only_the_configured_columns():
    properties = _provider(["name"])._station_properties(
        {"name": "NM-28368", "thing_type": "spring", "well_depth": 10.0}
    )

    assert properties == {"name": "NM-28368"}


# ---------------------------------------------------------------- instances


def test_provider_implements_pygeoapis_instance_contract():
    """The method names pygeoapi actually calls.

    BaseEDRProvider.instances/instance *return* a NotImplementedError rather
    than raising one, so a provider that spells these get_instances/
    get_instance overrides nothing and fails silently at the API layer:
    /instances iterates the NotImplementedError object (TypeError -> 500), and
    /instances/{id}/... validates the id against a truthy object, accepting
    anything.
    """
    from pygeoapi.provider.base_edr import BaseEDRProvider

    for name in ("instances", "instance"):
        assert name in StationEDRProvider.__dict__, (
            f"StationEDRProvider must override {name}() -- pygeoapi calls that "
            "name, and the base implementation returns a NotImplementedError "
            "object instead of raising."
        )
        assert getattr(StationEDRProvider, name) is not getattr(BaseEDRProvider, name)


def test_instances_are_empty_without_an_instance_field():
    # ogc_water_chemistry has no deployments, so its provider declares no
    # instance_field and must report an empty list rather than querying.
    provider = object.__new__(StationEDRProvider)
    provider.instance_field = None

    assert provider.instances() == []


def test_instance_validation_compares_as_strings(monkeypatch):
    # instances() reports identifiers as strings; the id arrives from the URL
    # as a string too, but an int must not slip through as valid.
    provider = object.__new__(StationEDRProvider)
    provider.instance_field = "deployment_id"
    monkeypatch.setattr(StationEDRProvider, "instances", lambda self: ["7", "9"])

    assert provider.instance("7") is True
    assert provider.instance(7) is True
    assert provider.instance("8") is False


# --------------------------------------------------------------- parameters


def test_one_parameter_set_yields_a_range_per_distinct_name(edr_coverage_provider):
    provider = edr_coverage_provider("manual_waterlevels")

    coverage = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 1),
                "observation_value": 42.0,
                "observation_unit": "ft",
                "observation_parameter_name": "groundwater level below ground surface",
                "qualifier_value": "test qualifier",
                "qualifier_parameter_name": "groundwater level reason",
            },
            {
                "thing_id": 1,
                "name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 2),
                "observation_value": 8000.0,
                "observation_unit": "ft",
                "observation_parameter_name": "groundwater level way way way below ground surface",
                "qualifier_value": "test qualifier",
                "qualifier_parameter_name": "groundwater level reason",
            },
        ]
    )

    for p in [
        "groundwater level below ground surface",
        "groundwater level way way way below ground surface",
        "groundwater level reason",
    ]:
        parameter = coverage["parameters"][p]
        try:
            assert parameter["observedProperty"]["id"] == p
        except AssertionError as e:
            raise AssertionError(f"Parameter {p} failed validation: {e}")


def test_parameter_null_in_coverage_when_not_present(edr_coverage_provider):
    provider = edr_coverage_provider("manual_waterlevels")

    coverages = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 1),
                "observation_value": 42.0,
                "observation_unit": "ft",
                "observation_parameter_name": "groundwater level below ground surface",
                "qualifier_value": "test qualifier",
                "qualifier_parameter_name": "groundwater level reason",
            },
            {
                "thing_id": 1,
                "name": "Test well",
                "longitude": -106.0,
                "latitude": 34.0,
                "datetime": datetime(2024, 1, 2),
                "observation_value": 8000.0,
                "observation_unit": "ft",
                "observation_parameter_name": "groundwater level way way way below ground surface",
                "qualifier_value": "test way way way qualifier",
                "qualifier_parameter_name": "groundwater level reason",
            },
        ]
    )

    # ranges live on each station's coverage, not on the collection
    coverage = coverages["coverages"][0]
    assert coverage["ranges"]["groundwater level below ground surface"]["values"] == [
        42.0,
        None,
    ]
    assert coverage["ranges"]["groundwater level way way way below ground surface"][
        "values"
    ] == [None, 8000.0]
    assert coverage["ranges"]["groundwater level reason"]["values"] == [
        "test qualifier",
        "test way way way qualifier",
    ]


# ------------------------------------------------------- parameter-name (R9)

LEVEL = "groundwater level below ground surface"
REASON = "groundwater level reason"


def _reading(when: datetime, level: float, reason: str) -> dict:
    """One manual_waterlevels row: a level and its reason on the same row."""
    return {
        "thing_id": 1,
        "longitude": -106.0,
        "latitude": 34.0,
        "datetime": when,
        "observation_parameter_name": LEVEL,
        "observation_value": level,
        "observation_unit": "ft",
        "qualifier_parameter_name": REASON,
        "qualifier_value": reason,
    }


def test_parameter_name_publishes_only_the_selected_parameters(
    edr_coverage_provider,
):
    """A row matched by one parameter still carries the others; drop them.

    The SQL filter keeps whole rows, so a request for the level alone returns
    rows that also carry a reason. EDR never returns unselected parameters.
    """
    rows = [
        _reading(datetime(2024, 1, 1), 42.0, "Site was pumped"),
        _reading(datetime(2024, 1, 2), 43.0, "Site was pumped"),
    ]

    coverages = edr_coverage_provider("manual_waterlevels")._coverage_collection(
        rows, select_properties=[LEVEL]
    )

    assert set(coverages["parameters"]) == {LEVEL}
    coverage = coverages["coverages"][0]
    assert set(coverage["ranges"]) == {LEVEL}
    assert coverage["ranges"][LEVEL]["values"] == [42.0, 43.0]
    assert coverage["domain"]["axes"]["t"]["values"] == [
        "2024-01-01T00:00:00",
        "2024-01-02T00:00:00",
    ]


@pytest.mark.parametrize(
    "select_properties",
    [
        None,
        # pygeoapi's EDR handler passes `request.params.get('parameter-name')
        # or []`, so an unfiltered request arrives as an empty list, not None.
        [],
    ],
)
def test_no_parameter_name_publishes_every_parameter(
    edr_coverage_provider, select_properties
):
    rows = [_reading(datetime(2024, 1, 1), 42.0, "Site was pumped")]

    coverages = edr_coverage_provider("manual_waterlevels")._coverage_collection(
        rows, select_properties=select_properties
    )

    assert set(coverages["parameters"]) == {LEVEL, REASON}
    assert set(coverages["coverages"][0]["ranges"]) == {LEVEL, REASON}


# --------------------------------------------------------------- categories


def test_categories_from_lexicon_describe_only_informative_definitions():
    categories = categories_from_lexicon(
        [
            {"term": "Site was dry", "definition": "Site was dry"},
            {"term": "Site was pumped", "definition": "Pumping in the last hour."},
            {"term": "Obstructed", "definition": None},
        ]
    )

    assert categories == [
        {"id": "Site was dry", "label": {"en": "Site was dry"}},
        {
            "id": "Site was pumped",
            "label": {"en": "Site was pumped"},
            "description": {"en": "Pumping in the last hour."},
        },
        {"id": "Obstructed", "label": {"en": "Obstructed"}},
    ]


def test_only_categorical_parameters_carry_categories(edr_coverage_provider):
    """The reason lists its lexicon category's terms; the level has none.

    get_fields discovers the categories, keyed by parameter name; here they
    are set as discovery would leave them.
    """
    provider = edr_coverage_provider("manual_waterlevels")
    categories = [{"id": "Site was dry", "label": {"en": "Site was dry"}}]
    provider._lexicon_categories = {REASON: categories}

    parameters = provider._coverage_collection(
        [_reading(datetime(2024, 1, 1), 42.0, "Site was dry")]
    )["parameters"]

    assert parameters[REASON]["observedProperty"]["categories"] == categories
    assert "categories" not in parameters[LEVEL]["observedProperty"]


# ----------------------------------------------- duplicate axis values (rows)


def test_read_breaks_axis_ties_by_id(edr_coverage_provider, monkeypatch):
    """Rows at the same axis value come back in id order, every time.

    Without the tiebreaker Postgres may return tied rows in any order, so
    which duplicate _coverage_collection keeps would vary between requests.
    """
    provider = edr_coverage_provider("manual_waterlevels")
    provider.id_field = "id"
    captured = {}
    monkeypatch.setattr(
        provider, "_fetch", lambda sql, params=None: captured.setdefault("sql", sql)
    )

    provider._read(thing_id=1)

    assert captured["sql"].endswith("ORDER BY thing_id, datetime, id")


def test_duplicate_row_is_skipped_whole(edr_coverage_provider, caplog):
    """The first row at an axis value wins, value and qualifier together.

    A per-parameter check would keep the first row's level but could take the
    reason from a later row, pairing a level with another reading's reason.
    """
    when = datetime(2024, 1, 1)
    rows = [
        _reading(when, 42.0, "Site was pumped"),
        _reading(when, 99.0, "Site was dry"),
    ]

    with caplog.at_level(logging.WARNING, logger="core.edr_provider"):
        coverages = edr_coverage_provider("manual_waterlevels")._coverage_collection(
            rows
        )

    ranges = coverages["coverages"][0]["ranges"]
    assert ranges[LEVEL]["values"] == [42.0]
    assert ranges[REASON]["values"] == ["Site was pumped"]
    assert any("Duplicate row" in r.getMessage() for r in caplog.records)


def test_a_null_level_still_claims_its_axis_value(edr_coverage_provider):
    """A reason-only first row is not overwritten by a later duplicate.

    The old check (`values[i] is not None`) treated a null level as an empty
    slot and let the duplicate's level in beside the first row's reason.
    """
    when = datetime(2024, 1, 1)
    rows = [
        _reading(when, None, "Site was dry"),
        _reading(when, 99.0, "Site was pumped"),
    ]

    coverages = edr_coverage_provider("manual_waterlevels")._coverage_collection(rows)

    ranges = coverages["coverages"][0]["ranges"]
    assert ranges[LEVEL]["values"] == [None]
    assert ranges[REASON]["values"] == ["Site was dry"]


def test_long_rows_sharing_an_axis_value_are_not_duplicates(edr_coverage_provider):
    """In a long view, different parameters at one datetime are all kept.

    water_chemistry carries one analyte per row, so a sample's analytes share
    its datetime; only a repeat of the same parameter is a duplicate.
    """
    when = datetime(2024, 1, 1)

    def analyte(name, value):
        return {
            "thing_id": 1,
            "longitude": -106.0,
            "latitude": 34.0,
            "datetime": when,
            "parameter_name": name,
            "value": value,
            "unit": "mg/L",
        }

    rows = [analyte("Calcium", 12.0), analyte("Sodium", 30.0), analyte("Calcium", 99.0)]

    coverages = edr_coverage_provider("water_chemistry")._coverage_collection(rows)

    ranges = coverages["coverages"][0]["ranges"]
    assert ranges["Calcium"]["values"] == [12.0]
    assert ranges["Sodium"]["values"] == [30.0]


# Test that the keys in EDR_PROVIDER_COLLECTION_KEYS are correctly carried from the collection to the provider.
def _generated_providers(table_prefix: str) -> dict[str, dict]:
    """{collection id: provider entry} as pygeoapi will read them."""
    block = _edr_collections_block(
        host="db",
        port="5432",
        dbname="ocotillo",
        user="reader",
        password_placeholder="${PASSWORD}",
        table_prefix=table_prefix,
    )
    resources = yaml.safe_load(textwrap.dedent(block))
    return {cid: resource["providers"][0] for cid, resource in resources.items()}


@pytest.mark.parametrize("table_prefix", ["ogc_", "ogc_internal_"])
def test_generated_edr_providers_carry_the_collection_config(table_prefix):
    """Config in EDR_COLLECTIONS reaches the provider pygeoapi builds.

    pygeoapi constructs the provider from the generated YAML, not from
    EDR_COLLECTIONS, so a key that _edr_collections_block forgets to copy
    never reaches the provider -- and the unit tests, which set provider
    attributes by hand, cannot see that.
    """
    providers = _generated_providers(table_prefix)
    assert set(providers) == {c["id"] for c in EDR_COLLECTIONS}

    for collection in EDR_COLLECTIONS:
        provider = providers[collection["id"]]

        assert provider["type"] == "edr"
        assert provider["table"] == table_prefix + collection["table"].removeprefix(
            "ogc_"
        )
        # Every key is copied, None included (instance_field: null when a
        # collection has no instances), so each provider has the same shape.
        for key in EDR_PROVIDER_COLLECTION_KEYS:
            assert (
                provider[key] == collection[key]
            ), f"{collection['id']}: {key} did not reach the provider"


# ---------------------------------------------- OpenAPI: /locations parameters

_PARAMETER_NAME_REF = {
    "$ref": "https://schemas.opengis.net/ogcapi/edr/1.0/openapi/parameters/"
    "parameter-name.yaml"
}


def _locations_paths(parameters_by_collection: dict[str, list]) -> dict:
    """A minimal OpenAPI document with one /locations path per collection."""
    return {
        "paths": {
            f"/collections/{cid}/locations": {"get": {"parameters": parameters}}
            for cid, parameters in parameters_by_collection.items()
        }
    }


def test_parameter_name_is_added_to_each_edr_locations_path():
    oas = _locations_paths({c["id"]: [] for c in EDR_COLLECTIONS})

    _document_locations_parameter_name(oas)

    for collection in EDR_COLLECTIONS:
        parameters = oas["paths"][f"/collections/{collection['id']}/locations"]["get"][
            "parameters"
        ]
        assert parameters == [_PARAMETER_NAME_REF]


def test_parameter_name_is_listed_after_datetime_and_before_f():
    # The order pygeoapi generates for /locations, and for /locations/{locId}
    # (datetime, parameter-name, crs, f).
    bbox = {"$ref": "edr/parameters/bbox.yaml"}
    datetime_ = {"$ref": "features-1.yaml#/components/parameters/datetime"}
    format_ = {"$ref": "#/components/parameters/f"}
    collection_id = EDR_COLLECTIONS[0]["id"]
    oas = _locations_paths({collection_id: [bbox, datetime_, format_]})

    _document_locations_parameter_name(oas)

    parameters = oas["paths"][f"/collections/{collection_id}/locations"]["get"][
        "parameters"
    ]
    assert parameters == [bbox, datetime_, _PARAMETER_NAME_REF, format_]


@pytest.mark.parametrize(
    "native",
    [
        _PARAMETER_NAME_REF,
        # A future pygeoapi could inline the parameter instead of a $ref.
        {"name": "parameter-name", "in": "query", "schema": {"type": "string"}},
    ],
)
def test_parameter_name_is_not_duplicated_when_already_listed(native):
    """A pygeoapi upgrade that documents it natively keeps one entry."""
    collection_id = EDR_COLLECTIONS[0]["id"]
    oas = _locations_paths({collection_id: [native]})

    _document_locations_parameter_name(oas)

    parameters = oas["paths"][f"/collections/{collection_id}/locations"]["get"][
        "parameters"
    ]
    assert [p for p in parameters if _is_parameter_name(p)] == [native]


def test_skipped_edr_collections_are_left_out_of_the_document():
    # pygeoapi omits a collection whose backing view is missing; the amendment
    # must not invent a path for it.
    oas = {"paths": {}}

    _document_locations_parameter_name(oas)

    assert oas == {"paths": {}}


def test_one_unloadable_edr_collection_does_not_hide_the_others(monkeypatch):
    """Only the EDR collection whose provider raises is left out.

    pygeoapi's get_oas drops the whole EDR section when any one provider
    raises, so water_chemistry failing R13 used to strip manual_waterlevels'
    query paths too.
    """
    import pygeoapi.plugin

    from core.pygeoapi import _drop_unloadable_edr_collections

    def load_plugin(kind, provider_def):
        if provider_def["table"] == "ogc_water_chemistry":
            raise ValueError("parameter 'CF' has more than one unit")
        return object()

    monkeypatch.setattr(pygeoapi.plugin, "load_plugin", load_plugin)
    settings = {
        "resources": {
            "manual_waterlevels": {
                "providers": [{"type": "edr", "table": "ogc_manual_waterlevels"}]
            },
            "water_chemistry": {
                "providers": [{"type": "edr", "table": "ogc_water_chemistry"}]
            },
            "water_wells": {
                "providers": [{"type": "feature", "table": "ogc_water_wells"}]
            },
        }
    }

    _drop_unloadable_edr_collections(settings)

    assert set(settings["resources"]) == {"manual_waterlevels", "water_wells"}


# ------------------------------------------------------ one unit per parameter


def _discovering_provider(edr_coverage_provider, monkeypatch, collection_id, rows):
    """A provider whose discovery query (get_fields) returns ``rows``."""
    provider = edr_coverage_provider(collection_id)
    provider._fields = {}
    monkeypatch.setattr(provider, "_fetch", lambda sql, params=None: rows)
    return provider


def test_a_parameter_with_more_than_one_unit_is_not_published(
    edr_coverage_provider, monkeypatch, caplog
):
    """R13: every row of a parameter must share the unit, or it is dropped.

    Only that parameter goes; the rest of the collection is still published.
    """
    provider = _discovering_provider(
        edr_coverage_provider,
        monkeypatch,
        "water_chemistry",
        [
            {"parameter_name": "CF", "unit": "µS/cm"},
            {"parameter_name": "CF", "unit": "mS/cm"},
            {"parameter_name": "Calcium", "unit": "mg/L"},
        ],
    )

    with caplog.at_level(logging.WARNING, logger="core.edr_provider"):
        fields = provider.get_fields()

    assert set(fields) == {"Calcium"}
    assert fields["Calcium"]["x-ogc-unit"] == "mg/L"
    assert provider._dropped_parameters == {"CF"}
    assert any(
        "'CF'" in r.getMessage() and "more than one unit" in r.getMessage()
        for r in caplog.records
    )


def test_a_null_unit_beside_a_unit_is_a_second_unit(edr_coverage_provider, monkeypatch):
    """No exceptions: a row with no unit does not match a row with one."""
    provider = _discovering_provider(
        edr_coverage_provider,
        monkeypatch,
        "water_chemistry",
        [
            {"parameter_name": "NO3", "unit": "mg/L"},
            {"parameter_name": "NO3", "unit": None},
        ],
    )

    assert provider.get_fields() == {}
    assert provider._dropped_parameters == {"NO3"}


def test_a_parameter_without_a_unit_column_is_published_without_a_unit(
    edr_coverage_provider, monkeypatch
):
    """The reason has no unit column: one unit (none), so it is kept.

    The SQL selects NULL for it, which arrives as None -- it must not be
    published as an `x-ogc-unit` of None.
    """
    rows = {
        "observation_parameter_name": [
            {"parameter_name": LEVEL, "unit": "ft"},
        ],
        "qualifier_parameter_name": [
            {"parameter_name": REASON, "unit": None},
        ],
    }
    provider = edr_coverage_provider("manual_waterlevels")
    provider._fields = {}
    # the discovery query for each parameter column, matched on its name column
    monkeypatch.setattr(
        provider,
        "_fetch",
        lambda sql, params=None: next(v for k, v in rows.items() if k in sql),
    )
    # the reason is categorical, so discovery also reads its lexicon category;
    # that lookup is not what this test is about
    monkeypatch.setattr(
        provider,
        "_create_lexicon_categories",
        lambda category: [{"id": "Site was dry", "label": {"en": "Site was dry"}}],
    )

    fields = provider.get_fields()

    assert set(fields) == {LEVEL, REASON}
    assert fields[LEVEL]["x-ogc-unit"] == "ft"
    assert "x-ogc-unit" not in fields[REASON]
    assert provider._dropped_parameters == set()


def test_an_unpublished_parameter_is_left_out_of_coverages(edr_coverage_provider):
    """A dropped parameter on a row beside a published one is skipped alone."""
    provider = edr_coverage_provider("manual_waterlevels")
    provider._dropped_parameters = {LEVEL}

    coverages = provider._coverage_collection(
        [_reading(datetime(2024, 1, 1), 42.0, "Site was pumped")]
    )

    assert set(coverages["parameters"]) == {REASON}
    assert set(coverages["coverages"][0]["ranges"]) == {REASON}


def test_queries_skip_rows_carrying_only_unpublished_parameters(
    edr_coverage_provider,
):
    """/locations and the coverage queries never see an unpublished-only row,
    so a station whose only data is a dropped parameter is not listed."""
    provider = edr_coverage_provider("water_chemistry")
    provider._dropped_parameters = {"CF", "NO3"}

    clauses, params = provider._filters()

    assert clauses == [
        "((parameter_name IS NOT NULL AND NOT parameter_name = ANY(%s)))"
    ]
    assert params == [["CF", "NO3"]]
