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
"""Structural + unit tests for the NM_Wells Phase-1 staging mirror.

Covers SPEC §V invariants for the mirror schema, migrations and OGC views:

    V1  - all 18 NMW_* mirror tables exist with a primary key
    V2  - mirror load order respects parent->child (FK parent precedes child)
    V3  - migrations build all 8 OGC views
    V5  - the temperature-profile OGC view is MATERIALIZED
    V6  - each geothermal pygeoapi collection maps to an existing DB relation
    V10 - FK enforcement lives in the migration (DB-level FK constraints exist)

Full data round-trip against a real SQL dump is out of scope here (SPEC §T.T14);
the dump parser is unit-tested directly instead.
"""

import os

import pytest
import yaml
from sqlalchemy import inspect as sa_inspect, text

from db.engine import engine, session_ctx
from transfers.nmw_mirror_transfer import NMW_MIRROR_SPECS
from transfers.nmw_sql_dump import _parse_value, iter_table_rows

ROOT = os.path.dirname(os.path.dirname(__file__))

# DB relations created by the OGC-view migrations (d1e2f3a4b5c6, e2f3a4b5c6d7).
OGC_VIEWS = [
    "ogc_geothermal_wells_bht",
    "ogc_geothermal_wells_temperature_profile",  # MATERIALIZED
    "ogc_geothermal_wells_summary_heat_flow",
    "ogc_geothermal_wells_interval_heat_flow",
    "ogc_bht_measurements",
    "ogc_temp_depth_measurements",
    "ogc_heat_flow",
    "ogc_dst",
]
MATERIALIZED_VIEW = "ogc_geothermal_wells_temperature_profile"

# pygeoapi collections added by this PR and the DB relation each is backed by.
GEOTHERMAL_COLLECTIONS = {
    "geothermal_wells_bht": "ogc_geothermal_wells_bht",
    "geothermal_wells_temperature_profile": "ogc_geothermal_wells_temperature_profile",
    "bht_measurements": "ogc_bht_measurements",
    "temp_depth_measurements": "ogc_temp_depth_measurements",
    "heat_flow": "ogc_heat_flow",
    "dst": "ogc_dst",
}


def _mirror_tablenames() -> list[str]:
    return [spec.model.__tablename__ for spec in NMW_MIRROR_SPECS]


# --------------------------------------------------------------------------- V1
def test_all_mirror_tables_present_with_pk():
    """All 18 NMW_* mirror tables exist in the schema, each with a PK (V1)."""
    names = _mirror_tablenames()
    assert len(names) == 18, f"expected 18 mirror specs, got {len(names)}"

    insp = sa_inspect(engine)
    existing = set(insp.get_table_names())
    for table in names:
        assert table in existing, f"mirror table {table} missing from schema"
        pk = insp.get_pk_constraint(table)["constrained_columns"]
        assert pk, f"mirror table {table} has no primary key"


def test_well_headers_pk_is_well_data_id():
    """Spot-check that original SQL Server column names are preserved (V1)."""
    insp = sa_inspect(engine)
    pk = insp.get_pk_constraint("NMW_WellHeaders")["constrained_columns"]
    assert pk == ["WellDataID"]


# ----------------------------------------------------------------------- V2/V10
def test_mirror_tables_have_fk_constraints():
    """The migration creates DB-level FK constraints (V10) - at least one
    child table must carry a foreign key."""
    insp = sa_inspect(engine)
    total_fks = sum(len(insp.get_foreign_keys(t)) for t in _mirror_tablenames())
    assert total_fks > 0, "no FK constraints found on NMW_* mirror tables"


def test_fk_parent_loads_before_child():
    """Every FK parent table is loaded before its child in NMW_MIRROR_SPECS so
    the parent row exists when the child is inserted (V2)."""
    order = {name: i for i, name in enumerate(_mirror_tablenames())}
    insp = sa_inspect(engine)
    checked = 0
    for child in order:
        for fk in insp.get_foreign_keys(child):
            parent = fk["referred_table"]
            if parent not in order or parent == child:
                continue  # self-ref or FK to a non-mirror table
            checked += 1
            assert order[parent] <= order[child], (
                f"{parent} (parent) must load before {child} (child) "
                f"in NMW_MIRROR_SPECS"
            )
    assert checked > 0, "expected at least one intra-mirror FK to validate"


# --------------------------------------------------------------------------- V3
def test_ogc_views_exist():
    """All 8 OGC views built by the migrations exist as relations (V3)."""
    with session_ctx() as session:
        rows = session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "UNION SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'"
            )
        ).all()
    relations = {r[0] for r in rows}
    for view in OGC_VIEWS:
        assert view in relations, f"OGC view {view} missing"


# --------------------------------------------------------------------------- V5
def test_temperature_profile_is_materialized():
    """The temperature-profile view is MATERIALIZED so it can be refreshed
    after a mirror load (V5)."""
    with session_ctx() as session:
        names = {
            r[0]
            for r in session.execute(
                text("SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'")
            ).all()
        }
    assert MATERIALIZED_VIEW in names, f"{MATERIALIZED_VIEW} is not a materialized view"


# --------------------------------------------------------------------------- V6
class _Default(dict):
    """format_map() helper: unknown placeholders render empty."""

    def __missing__(self, key):  # noqa: D401
        return ""


def _load_pygeoapi_config() -> dict:
    """pygeoapi-config.yml is a ``{placeholder}`` template (see core/pygeoapi.py
    _write_config); substitute dummy values before parsing as YAML."""
    raw = open(os.path.join(ROOT, "core", "pygeoapi-config.yml")).read()
    rendered = raw.format_map(
        _Default(
            server_url="http://test",
            postgres_host="h",
            postgres_port="5432",
            postgres_db="d",
            postgres_user="u",
            postgres_password_env="p",
            thing_collections_block="",
        )
    )
    return yaml.safe_load(rendered)


def test_geothermal_collections_back_existing_relations():
    """Each new geothermal pygeoapi collection points at a DB relation that
    actually exists (V6)."""
    cfg = _load_pygeoapi_config()
    resources = cfg["resources"]

    with session_ctx() as session:
        rows = session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "UNION SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'"
            )
        ).all()
    relations = {r[0] for r in rows}

    for coll, expected_table in GEOTHERMAL_COLLECTIONS.items():
        assert coll in resources, f"collection {coll} missing from pygeoapi config"
        tables = {
            p.get("table")
            for p in resources[coll].get("providers", [])
            if p.get("table")
        }
        assert (
            expected_table in tables
        ), f"collection {coll} should be backed by {expected_table}, got {tables}"
        assert (
            expected_table in relations
        ), f"backing relation {expected_table} for {coll} does not exist in DB"


# ----------------------------------------------------------------- dump parser
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("NULL", None),
        ("null", None),
        ("123", 123),
        ("-5", -5),
        ("-1.5", -1.5),
        ("'abc'", "abc"),
        ("N'abc'", "abc"),
        ("'O''Brien'", "O'Brien"),  # doubled '' unescaped
        ("CAST(42 AS int)", 42),
        ("CAST(N'x' AS nvarchar(10))", "x"),
        ("0xDEADBEEF", None),  # binary / rowversion not mirrored
    ],
)
def test_parse_value_coercion(raw, expected):
    assert _parse_value(raw) == expected


def test_iter_table_rows_parses_inserts(tmp_path):
    """iter_table_rows decodes column/value pairs from SSMS INSERT statements."""
    dump = tmp_path / "dump.sql"
    dump.write_text(
        "INSERT [dbo].[tbl_demo] ([OBJECTID], [Name], [Note]) "
        "VALUES (1, N'alpha', NULL), (2, 'beta', CAST(N'c' AS nvarchar(1)));\n",
        encoding="utf-8",
    )
    rows = list(iter_table_rows(str(dump), "tbl_demo"))
    assert rows == [
        {"OBJECTID": 1, "Name": "alpha", "Note": None},
        {"OBJECTID": 2, "Name": "beta", "Note": "c"},
    ]


# ------------------------------------------------------ regression: FK truncate
def test_truncate_referenced_parent_needs_cascade():
    """A bare TRUNCATE of an FK-referenced mirror parent is rejected; the loader
    must use CASCADE (V13 / B2). Guards the dump-load reload path."""
    import sqlalchemy.exc

    # Bare truncate of the FK-referenced parent should error...
    with session_ctx() as session:
        with pytest.raises(sqlalchemy.exc.DBAPIError):
            session.execute(text('TRUNCATE TABLE "NMW_WellHeaders"'))
    # ...while CASCADE (what the loader does) succeeds.
    with session_ctx() as session:
        session.execute(text('TRUNCATE TABLE "NMW_WellHeaders" CASCADE'))
        session.commit()


# --------------------------------------------- regression: one feature per well
def test_bht_view_one_feature_per_well_with_duplicate_locations():
    """Two location rows for one WellDataID must not multiply BHT features or
    inflate bht_count; the view dedups locations via DISTINCT ON (V14 / B3)."""
    wid = "11111111-1111-1111-1111-111111111111"
    rsid = "22222222-2222-2222-2222-222222222222"
    ssid = "33333333-3333-3333-3333-333333333333"
    bht = "44444444-4444-4444-4444-444444444444"
    with session_ctx() as session:
        session.execute(
            text('INSERT INTO "NMW_WellHeaders" ("WellDataID") VALUES (:w)'),
            {"w": wid},
        )
        # TWO location rows, same WellDataID, valid coords (the bug trigger).
        session.execute(
            text(
                'INSERT INTO "NMW_WellLocations" '
                '("OBJECTID","WellDataID","Lat_dd83","Long_dd83") VALUES '
                "(901,:w,33.0,-107.0),(902,:w,33.0,-107.0)"
            ),
            {"w": wid},
        )
        session.execute(
            text(
                'INSERT INTO "NMW_WellRecords" ("RecrdSetID","WellDataID") '
                "VALUES (:r,:w)"
            ),
            {"r": rsid, "w": wid},
        )
        session.execute(
            text(
                'INSERT INTO "NMW_WellSamples" ("SamplSetID","RecrdsetID") '
                "VALUES (:s,:r)"
            ),
            {"s": ssid, "r": rsid},
        )
        session.execute(
            text(
                'INSERT INTO "NMW_GtBhtHeaders" ("BHTGUID","SamplSetID") '
                "VALUES (:b,:s)"
            ),
            {"b": bht, "s": ssid},
        )
        session.execute(
            text(
                'INSERT INTO "NMW_GtBhtData" ("OBJECTID","BHTGUID","BHT","Depth") '
                "VALUES (911,:b,150.0,1000.0)"
            ),
            {"b": bht},
        )
        session.commit()
    try:
        with session_ctx() as session:
            rows = session.execute(
                text(
                    'SELECT bht_count FROM "ogc_geothermal_wells_bht" '
                    "WHERE well_data_id = :w"
                ),
                {"w": wid},
            ).all()
        assert len(rows) == 1, f"expected one feature per well, got {len(rows)}"
        assert (
            rows[0][0] == 1
        ), f"bht_count inflated by duplicate locations: {rows[0][0]}"
    finally:
        with session_ctx() as session:
            session.execute(text('TRUNCATE TABLE "NMW_WellHeaders" CASCADE'))
            session.commit()


# ============= EOF =============================================
