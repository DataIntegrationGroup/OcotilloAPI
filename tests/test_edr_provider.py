"""Unit tests for the EDR provider, without a database.

Station metadata on /locations comes from each collection's station_properties
config: the listed view columns are published as GeoJSON properties under
their own names.
"""

from datetime import datetime
import textwrap
import pytest
import yaml

from core.edr_provider import StationEDRProvider, categories_from_lexicon
from core.pygeoapi import (
    EDR_COLLECTIONS,
    EDR_PROVIDER_COLLECTION_KEYS,
    _edr_collections_block,
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
            assert parameter["observedProperty"]["label"]["en"] == p
            assert parameter["description"]["en"].startswith(p)
        except AssertionError:
            raise AssertionError(f"Parameter {p} failed validation")


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
    """The reason lists its lexicon category's terms; the level has none."""
    provider = edr_coverage_provider("manual_waterlevels")
    looked_up = []

    def fake_lexicon_categories(lexicon_category):
        looked_up.append(lexicon_category)
        return [{"id": "Site was dry", "label": {"en": "Site was dry"}}]

    provider._lexicon_categories = fake_lexicon_categories

    parameters = provider._coverage_collection(
        [_reading(datetime(2024, 1, 1), 42.0, "Site was dry")]
    )["parameters"]

    assert looked_up == ["groundwater_level_reason"]
    assert parameters[REASON]["observedProperty"]["categories"] == [
        {"id": "Site was dry", "label": {"en": "Site was dry"}}
    ]
    assert "categories" not in parameters[LEVEL]["observedProperty"]


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
