"""Unit tests for the EDR provider's optional station metadata.

The chemistry views (d9e0f1a2b3c4) carry thing_type because they span wells and
springs; ogc_manual_waterlevels does not. The provider detects the column rather than
assuming it, so these cover both shapes without needing a database.
"""

from datetime import datetime

from core.edr_provider import PointSeriesEDRProvider
from core.pygeoapi import EDR_COLLECTIONS


def _provider(has_thing_type: bool) -> PointSeriesEDRProvider:
    # Bypass __init__: it connects to Postgres to read fields and detect
    # columns, and neither is what these tests are about.
    provider = object.__new__(PointSeriesEDRProvider)
    provider._has_thing_type = has_thing_type
    return provider


def test_station_properties_includes_thing_type_when_the_view_has_it():
    properties = _provider(True)._station_properties(
        {"station_name": "NM-28368", "thing_type": "spring"}
    )

    assert properties == {"name": "NM-28368", "thing_type": "spring"}


def test_station_properties_omits_thing_type_when_the_view_lacks_it():
    # ogc_manual_waterlevels has no thing_type column, so the row has no such key --
    # reading it unconditionally would raise instead of degrading.
    properties = _provider(False)._station_properties({"station_name": "NM-28368"})

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
        assert name in PointSeriesEDRProvider.__dict__, (
            f"PointSeriesEDRProvider must override {name}() -- pygeoapi calls that "
            "name, and the base implementation returns a NotImplementedError "
            "object instead of raising."
        )
        assert getattr(PointSeriesEDRProvider, name) is not getattr(
            BaseEDRProvider, name
        )


def test_instances_are_empty_without_an_instance_field():
    # ogc_water_chemistry has no deployments, so its provider declares no
    # instance_field and must report an empty list rather than querying.
    provider = object.__new__(PointSeriesEDRProvider)
    provider.instance_field = None

    assert provider.instances() == []


def test_instance_validation_compares_as_strings(monkeypatch):
    # instances() reports identifiers as strings; the id arrives from the URL
    # as a string too, but an int must not slip through as valid.
    provider = object.__new__(PointSeriesEDRProvider)
    provider.instance_field = "deployment_id"
    monkeypatch.setattr(PointSeriesEDRProvider, "instances", lambda self: ["7", "9"])

    assert provider.instance("7") is True
    assert provider.instance(7) is True
    assert provider.instance("8") is False


# --------------------------------------------------------------- parameters


def test_one_parameter_set_yields_a_range_per_distinct_name():
    collection = next(c for c in EDR_COLLECTIONS if c["id"] == "manual_waterlevels")

    provider = object.__new__(PointSeriesEDRProvider)
    provider.table = collection["table"]
    provider.parameter_columns = collection["parameter_columns"]
    provider.independent_axis = collection["independent_axis"]

    coverage = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "station_name": "Test well",
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
                "station_name": "Test well",
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
            assert parameter["observedProperty"]["label"]["en"] == p.capitalize()
            assert parameter["description"]["en"].startswith(p.capitalize())
        except AssertionError:
            raise AssertionError(f"Parameter {p} failed validation")


def test_parameter_null_in_coverage_when_not_present():
    collection = next(c for c in EDR_COLLECTIONS if c["id"] == "manual_waterlevels")

    provider = object.__new__(PointSeriesEDRProvider)
    provider.table = collection["table"]
    provider.parameter_columns = collection["parameter_columns"]
    provider.independent_axis = collection["independent_axis"]

    coverage = provider._coverage_collection(
        [
            {
                "thing_id": 1,
                "station_name": "Test well",
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
                "station_name": "Test well",
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
