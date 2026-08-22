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
"""Unit tests for core/ogc_field_metadata.py. No database, no pygeoapi."""

import pytest

from core.ogc_field_metadata import (
    ALLOWED_KEYS,
    default_title,
    describe_fields,
    load_field_metadata,
    strip_table_prefix,
    table_entries,
)


def test_metadata_file_loads_and_validates():
    metadata = load_field_metadata()

    assert "_defaults" in metadata
    for table, fields in metadata.items():
        for field, entry in fields.items():
            assert entry["title"], f"{table}.{field} has no title"
            assert not set(entry) - ALLOWED_KEYS


@pytest.mark.parametrize(
    "table,expected",
    [
        ("ogc_water_wells", "water_wells"),
        ("ogc_internal_water_wells", "water_wells"),
        ("water_wells", "water_wells"),
        # "ogc_internal_" has to be stripped before "ogc_", or the internal
        # tables would look up an "internal_water_wells" block that has no
        # entries and every field would fall back.
        ("ogc_internal_other_things", "other_things"),
    ],
)
def test_strip_table_prefix(table, expected):
    assert strip_table_prefix(table) == expected


def test_default_title():
    assert default_title("depth_to_water_bgs") == "Depth To Water Bgs"
    assert default_title("id") == "Id"


def test_table_entries_merge_defaults_under_the_table_block():
    entries = table_entries("ogc_water_well_summary")

    # From _defaults.
    assert entries["id"]["title"] == "Feature ID"
    # From the table block.
    assert entries["total_water_levels"]["title"] == "Water-level measurement count"


def test_table_entries_prefer_the_table_block_over_defaults():
    # locations.description is the site description, not any default.
    assert table_entries("ogc_locations")["description"]["title"] == "Site description"
    assert table_entries("ogc_project_areas")["description"]["title"] == (
        "Project description"
    )


def test_describe_fields_annotates_documented_columns():
    described = describe_fields(
        "ogc_internal_water_wells",
        {"well_depth": {"type": "number", "format": None}},
    )

    field = described["well_depth"]
    assert field["type"] == "number"
    assert field["format"] is None
    assert field["title"] == "Well depth"
    assert field["description"].startswith("Total depth of the finished well")
    assert field["x-ogc-unit"] == "https://qudt.org/vocab/unit/FT"
    assert field["x-ogc-unitLang"] == "QUDT"


def test_describe_fields_falls_back_without_raising(caplog):
    described = describe_fields(
        "ogc_water_wells", {"not_documented": {"type": "string"}}
    )

    assert described["not_documented"] == {
        "type": "string",
        "title": "Not Documented",
    }
    assert "not_documented" in caplog.text


def test_describe_fields_returns_fresh_dicts():
    # pygeoapi's get_collection_schema assigns the provider's field dict into
    # its response and then mutates it in place. Handing out references into
    # the cached YAML would let one request's mutations leak into the next.
    fields = {"well_depth": {"type": "number"}}

    first = describe_fields("ogc_water_wells", fields)
    first["well_depth"]["x-ogc-role"] = "id"
    first["well_depth"].pop("description")

    second = describe_fields("ogc_water_wells", fields)
    assert "x-ogc-role" not in second["well_depth"]
    assert second["well_depth"]["description"]
    assert fields["well_depth"] == {"type": "number"}


def test_describe_fields_tolerates_empty_input():
    assert describe_fields("ogc_water_wells", {}) == {}
    assert describe_fields("ogc_water_wells", None) == {}
