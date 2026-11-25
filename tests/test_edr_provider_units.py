"""R13 against Postgres: a parameter reporting more than one unit is published
in its most common unit, and rows in any other unit are skipped.

test_edr_provider.py checks the SQL as strings; this runs it, because the row
filter's behaviour depends on how Postgres resolves column names -- an alias
column named like a view column silently captures the reference.
"""

import os

import pytest
from sqlalchemy import text

from core.edr_provider import StationEDRProvider
from core.pygeoapi import EDR_COLLECTIONS
from db.engine import session_ctx

TABLE = "test_edr_mixed_units"


@pytest.fixture()
def mixed_unit_provider():
    """A long (water_chemistry-shaped) table whose unit column is `unit`.

    NO3 has 3 rows with no unit and 2 in mg/L, so its kept unit is None:
      - well 10: one unitless row, one mg/L row
      - well 20: only unitless rows
      - well 30: only mg/L rows -> nothing publishable
    """
    with session_ctx() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        session.execute(
            text(
                f"CREATE TABLE {TABLE} AS SELECT * FROM (VALUES "
                "(1, 10, 'W10', 'water well', -106.0, 34.0, "
                "  timestamp '2024-01-01', 'NO3', 1.0, NULL::text), "
                "(2, 10, 'W10', 'water well', -106.0, 34.0, "
                "  timestamp '2024-01-02', 'NO3', 2.0, 'mg/L'), "
                "(3, 20, 'W20', 'water well', -107.0, 35.0, "
                "  timestamp '2024-01-01', 'NO3', 3.0, NULL), "
                "(4, 20, 'W20', 'water well', -107.0, 35.0, "
                "  timestamp '2024-01-02', 'NO3', 4.0, NULL), "
                "(5, 30, 'W30', 'water well', -108.0, 36.0, "
                "  timestamp '2024-01-01', 'NO3', 5.0, 'mg/L')"
                ") AS v(id, thing_id, name, thing_type, longitude, latitude, "
                "datetime, parameter_name, value, unit)"
            )
        )
        session.commit()

    collection = next(c for c in EDR_COLLECTIONS if c["id"] == "water_chemistry")
    provider = StationEDRProvider(
        {
            "name": "core.edr_provider.StationEDRProvider",
            "type": "edr",
            "id_field": "id",
            "table": TABLE,
            "data": {
                "host": os.environ.get("POSTGRES_HOST", "localhost"),
                "port": os.environ.get("POSTGRES_PORT", "5432"),
                "dbname": os.environ["POSTGRES_DB"],
                "user": os.environ.get("POSTGRES_USER", ""),
                "password": os.environ.get("POSTGRES_PASSWORD", ""),
            },
            "parameter_columns": collection["parameter_columns"],
            "station_properties": ["name"],
            "independent_axis": collection["independent_axis"],
            "instance_field": None,
        }
    )
    yield provider

    with session_ctx() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        session.commit()


def test_discovery_keeps_the_most_common_unit(mixed_unit_provider):
    assert mixed_unit_provider._kept_units == {"NO3": None}
    assert "x-ogc-unit" not in mixed_unit_provider.get_fields()["NO3"]


def test_locations_lists_only_wells_with_kept_unit_rows(mixed_unit_provider):
    features = mixed_unit_provider.locations()["features"]

    assert sorted(f["id"] for f in features) == [10, 20]


def test_coverage_skips_off_unit_rows(mixed_unit_provider):
    """The mg/L reading is filtered out in SQL, so its time step is not on
    the axis at all, rather than appearing as a null."""
    coverage = mixed_unit_provider.locations(location_id=10)["coverages"][0]

    assert coverage["domain"]["axes"]["t"]["values"] == ["2024-01-01T00:00:00"]
    assert coverage["ranges"]["NO3"]["values"] == [1.0]


WIDE_TABLE = "test_edr_mixed_units_wide"


@pytest.fixture()
def mixed_unit_wide_provider():
    """A manual_waterlevels-shaped table: a level and its reason per row.

    The level is in ft on 2 rows and m on 1, so ft is kept and the m row --
    reason included -- is skipped. Well 20's only reading is in m.
    """
    with session_ctx() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {WIDE_TABLE}"))
        session.execute(
            text(
                f"CREATE TABLE {WIDE_TABLE} AS SELECT * FROM (VALUES "
                "(1, 10, 'W10', 'water well', -106.0, 34.0, timestamp '2024-01-01', "
                "  'level', 5.0, 'ft', 'reason', 'Site was dry'), "
                "(2, 10, 'W10', 'water well', -106.0, 34.0, timestamp '2024-01-02', "
                "  'level', 1.5, 'm', 'reason', 'Site was pumped'), "
                "(3, 10, 'W10', 'water well', -106.0, 34.0, timestamp '2024-01-03', "
                "  'level', 6.0, 'ft', 'reason', NULL), "
                "(4, 20, 'W20', 'water well', -107.0, 35.0, timestamp '2024-01-01', "
                "  'level', 2.0, 'm', 'reason', 'Site was pumped')"
                ") AS v(id, thing_id, name, thing_type, longitude, latitude, datetime, "
                "observation_parameter_name, observation_value, observation_unit, "
                "qualifier_parameter_name, qualifier_value)"
            )
        )
        session.commit()

    collection = next(c for c in EDR_COLLECTIONS if c["id"] == "manual_waterlevels")
    provider = StationEDRProvider(
        {
            "name": "core.edr_provider.StationEDRProvider",
            "type": "edr",
            "id_field": "id",
            "table": WIDE_TABLE,
            "data": {
                "host": os.environ.get("POSTGRES_HOST", "localhost"),
                "port": os.environ.get("POSTGRES_PORT", "5432"),
                "dbname": os.environ["POSTGRES_DB"],
                "user": os.environ.get("POSTGRES_USER", ""),
                "password": os.environ.get("POSTGRES_PASSWORD", ""),
            },
            "parameter_columns": [
                {**c, "lexicon_category": None} for c in collection["parameter_columns"]
            ],
            "station_properties": ["name"],
            "independent_axis": collection["independent_axis"],
            "instance_field": None,
        }
    )
    yield provider

    with session_ctx() as session:
        session.execute(text(f"DROP TABLE IF EXISTS {WIDE_TABLE}"))
        session.commit()


def test_an_off_unit_level_drops_its_reason_too(mixed_unit_wide_provider):
    provider = mixed_unit_wide_provider
    assert provider._kept_units == {"level": "ft"}

    # well 20's only reading is off-unit, even when asking for the reason
    assert [f["id"] for f in provider.locations()["features"]] == [10]
    assert [
        f["id"] for f in provider.locations(select_properties=["reason"])["features"]
    ] == [10]

    coverage = provider.locations(location_id=10)["coverages"][0]
    assert coverage["domain"]["axes"]["t"]["values"] == [
        "2024-01-01T00:00:00",
        "2024-01-03T00:00:00",
    ]
    assert coverage["ranges"]["level"]["values"] == [5.0, 6.0]
    assert coverage["ranges"]["reason"]["values"] == ["Site was dry", None]
