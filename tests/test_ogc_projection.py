# ===============================================================================
# Copyright 2025 ross
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
"""The public OGC collections, under the projection chokepoint (ADR5, A.2).

Two of these pin leaks that were live before the allowlist existed:
ogc_well_water_column published nma_pk_welldata, and
ogc_temp_depth_measurements published entered_by, a staff member's name.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text

from core.pygeoapi import THING_COLLECTIONS
from db.engine import session_ctx
from tests import client
from services.field_projection import (
    ogc_allowlist,
    ogc_collection_tables,
    ogc_never_public,
)

PUBLIC_CONFIG = Path(__file__).parent.parent / "core" / "pygeoapi-config.yml"
# The EDR collections are wired in core/pygeoapi.py rather than the YAML.
EDR_TABLES = ("ogc_waterlevels", "ogc_water_chemistry")

COLUMNS_QUERY = text(
    """
    select a.attname
    from pg_attribute a
    join pg_class c on c.oid = a.attrelid
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = :relation
      and a.attnum > 0
      and not a.attisdropped
    """
)


def public_tables() -> list:
    """Every table the public mount serves.

    Three sources, and missing the third is how eleven collections published
    nma_pk_welldata unnoticed: the YAML config, the thing collections built in
    core/pygeoapi.py, and the EDR collections wired there too.
    """
    configured = set(re.findall(r"table: (ogc_[a-z_]+)", PUBLIC_CONFIG.read_text()))
    things = {
        "ogc_" + collection["id"]
        for collection in THING_COLLECTIONS
        if not collection.get("internal_only")
    }
    return sorted(configured | things | set(EDR_TABLES))


def live_columns(relation: str) -> set:
    with session_ctx() as session:
        return set(session.execute(COLUMNS_QUERY, {"relation": relation}).scalars())


# ------ every public collection is projected ----------


@pytest.mark.parametrize("table", public_tables())
def test_every_public_collection_has_an_allowlist(table):
    """A collection with no entry publishes nothing. Fail here, not in prod."""
    assert table in ogc_collection_tables(), (
        f"{table} is served publicly but has no entry in "
        "core/field-allowlists.yml, so it would publish no properties."
    )


@pytest.mark.parametrize("table", public_tables())
def test_an_allowlist_never_names_a_never_public_column(table):
    assert not ogc_allowlist(table) & ogc_never_public()


@pytest.mark.parametrize("table", public_tables())
def test_an_allowlist_only_names_columns_the_view_has(table):
    """A stale name would make pygeoapi select a column that is not there."""
    assert ogc_allowlist(table) <= live_columns(table)


@pytest.mark.parametrize("table", public_tables())
def test_no_never_public_column_survives_into_a_published_collection(table):
    """The guard that matters: whatever the view grew, it is not published."""
    published = ogc_allowlist(table)
    assert not (live_columns(table) & ogc_never_public() & published)


# ------ the leaks this closed ----------


@pytest.mark.parametrize(
    "table",
    [
        "ogc_well_water_column",
        "ogc_water_wells",
        "ogc_springs",
        "ogc_meteorological_stations",
    ],
)
def test_the_thing_layers_no_longer_publish_the_legacy_key(table):
    """Eleven public collections carried nma_pk_welldata before this."""
    assert "nma_pk_welldata" in live_columns(table)
    assert "nma_pk_welldata" not in ogc_allowlist(table)


def test_the_geothermal_layer_no_longer_publishes_who_typed_the_record():
    assert "entered_by" in live_columns("ogc_temp_depth_measurements")
    assert "entered_by" not in ogc_allowlist("ogc_temp_depth_measurements")


# ------ what is and is not projected ----------


def test_the_internal_mount_is_not_projected():
    """Authenticated staff see the whole view; per-role rules are not built."""
    assert ogc_allowlist("ogc_internal_locations") is None


def test_an_unlisted_public_collection_publishes_nothing():
    """Default deny, rather than falling back to everything."""
    assert ogc_allowlist("ogc_collection_nobody_configured") == frozenset()


# ------ through the mounted service ----------


def _json(path):
    response = client.get(path, headers={"Accept": "application/json"})
    assert response.status_code == 200, response.text
    return response.text


@pytest.mark.parametrize(
    "collection,hidden,published",
    [
        ("well_water_column", "nma_pk_welldata", "well_depth"),
        ("temp_depth_measurements", "entered_by", "depth"),
    ],
)
def test_the_mount_publishes_the_allowlist_and_nothing_else(
    collection, hidden, published
):
    """Not just absent from features: absent from the schema and the
    queryables too, so a filter cannot probe for it either."""
    for path in (
        f"/ogcapi/collections/{collection}/schema",
        f"/ogcapi/collections/{collection}/queryables",
        f"/ogcapi/collections/{collection}/items?limit=1",
    ):
        body = _json(path)
        assert hidden not in body, f"{hidden} leaked through {path}"

    # The collection still works; this is projection, not breakage.
    assert published in _json(f"/ogcapi/collections/{collection}/schema")


def test_release_status_is_still_published():
    """The filter column stays visible; consumers read it to know what they
    have, and hiding it would be a behavior change nobody asked for."""
    assert "release_status" in ogc_allowlist("ogc_waterlevels")
