"""Unit tests for the EDR provider's optional station metadata.

The chemistry views (d9e0f1a2b3c4) carry thing_type because they span wells and
springs; ogc_waterlevels does not. The provider detects the column rather than
assuming it, so these cover both shapes without needing a database.
"""

from core.edr_provider import WaterEDRProvider


def _provider(has_thing_type: bool) -> WaterEDRProvider:
    # Bypass __init__: it connects to Postgres to read fields and detect
    # columns, and neither is what these tests are about.
    provider = object.__new__(WaterEDRProvider)
    provider._has_thing_type = has_thing_type
    return provider


def test_station_properties_includes_thing_type_when_the_view_has_it():
    properties = _provider(True)._station_properties(
        {"station_name": "NM-28368", "thing_type": "spring"}
    )

    assert properties == {"name": "NM-28368", "thing_type": "spring"}


def test_station_properties_omits_thing_type_when_the_view_lacks_it():
    # ogc_waterlevels has no thing_type column, so the row has no such key --
    # reading it unconditionally would raise instead of degrading.
    properties = _provider(False)._station_properties({"station_name": "NM-28368"})

    assert properties == {"name": "NM-28368"}
