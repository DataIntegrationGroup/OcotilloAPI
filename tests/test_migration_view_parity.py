"""Drift detection between the public (A1) and internal (A11) OGC migrations.

The two chemistry pivot views (major/minor) are dominated by long
analyte-alias CASE-mapping blocks that encode real lab-data business
knowledge. Because this codebase keeps Alembic migrations self-contained
with no cross-migration imports, that logic is duplicated rather than
shared between f4a5b6c7d8e9 (public) and 2d3c3a268652 (internal). If someone
fixes an analyte mapping in one file without the other, the public and
internal chemistry layers silently diverge -- this test turns that into a
loud, specific CI failure instead.

The minor chemistry comparisons guard superseded copies. cab78adfe059 rebuilt
both minor views (adding tritium) from one shared builder, so the live
definition lives there and can't drift between mounts. Change the minor
analyte mapping in a new migration copied from cab78adfe059, not in these two
files: editing them keeps this test green and changes nothing in the database.
The major chemistry comparisons still guard the live definitions.
"""

import ast
from pathlib import Path

import pytest
from sqlalchemy import text

from core.pygeoapi import EDR_COLLECTIONS
from db.engine import session_ctx

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
PUBLIC_MIGRATION = (
    VERSIONS_DIR / "f4a5b6c7d8e9_apply_public_release_status_filter_to_ogc_views.py"
)
INTERNAL_MIGRATION = VERSIONS_DIR / "2d3c3a268652_create_internal_ogc_views.py"

# Substrings that are expected to differ between the two files -- normalized
# away before comparison. Order matters: the internal_ variant must be
# stripped before its shorter public counterpart could ever match it.
NAME_SUBSTITUTIONS = [
    ("ogc_internal_major_chemistry_results", "ogc_major_chemistry_results"),
    ("ogc_internal_minor_chemistry_wells", "ogc_minor_chemistry_wells"),
]

COMPARED_NAMES = [
    "STATIC_ANALYTE_COLUMNS_MAJOR",
    "STATIC_ANALYTE_COLUMNS_MINOR",
    "_major_chemistry_select_columns",
    "_major_chemistry_unit_columns",
    "_minor_chemistry_value_columns",
    "_minor_chemistry_unit_columns",
    "_create_major_chemistry_results_view",
    "_create_minor_chemistry_wells_view",
]


def _get_node_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node)
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if name in targets:
                return ast.get_source_segment(source, node)
        # STATIC_ANALYTE_COLUMNS_MAJOR/MINOR are annotated assignments
        # (`NAME: list[...] = [...]`), which parse as AnnAssign, not Assign.
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                return ast.get_source_segment(source, node)
    raise AssertionError(f"{name!r} not found in {path}")


def _normalize(source: str) -> str:
    for internal, public in NAME_SUBSTITUTIONS:
        source = source.replace(internal, public)
    return source


@pytest.mark.parametrize("name", COMPARED_NAMES)
def test_analyte_mapping_matches_between_public_and_internal_migrations(name):
    public_source = _normalize(_get_node_source(PUBLIC_MIGRATION, name))
    internal_source = _normalize(_get_node_source(INTERNAL_MIGRATION, name))
    assert public_source == internal_source, (
        f"{name} has drifted between the public (f4a5b6c7d8e9) and internal "
        "(2d3c3a268652) OGC migrations -- if this is a genuine analyte-mapping "
        "fix, apply it to both files."
    )


# Internal-only by design: carries landowner PII and must never have a public
# twin (see docs/water-well-field-operations-layer.md).
INTERNAL_ONLY = {"water_well_field_operations", "water_well_field_operations_stats"}

# Public relations deliberately without an internal mirror. Each entry needs a reason.
# Each geothermal view has no release filter so an internal mirror would be identical
# - bht_measurements: geothermal
# - dst: geothermal
# - geothermal_wells_bht: geothermal
# - geothermal_wells_interval_heat_flow: geothermal
# - geothermal_wells_summary_heat_flow: geothermal
# - geothermal_wells_temperature_profile: geothermal
# - heat_flow: geothermal
# - temp_depth_measurements: geothermal
PUBLIC_ONLY: set[str] = {
    "bht_measurements",
    "dst",
    "geothermal_wells_bht",
    "geothermal_wells_interval_heat_flow",
    "geothermal_wells_summary_heat_flow",
    "geothermal_wells_temperature_profile",
    "heat_flow",
    "temp_depth_measurements",
}


def _ogc_relations(session) -> tuple[set[str], set[str]]:
    rows = session.execute(
        text(
            "SELECT viewname AS name FROM pg_views WHERE schemaname = 'public' "
            "UNION SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'"
        )
    ).scalars()
    public, internal = set(), set()
    for name in rows:
        if name.startswith("ogc_internal_"):
            internal.add(name.removeprefix("ogc_internal_"))
        elif name.startswith("ogc_"):
            public.add(name.removeprefix("ogc_"))
    return public, internal


def test_every_public_ogc_relation_has_an_internal_mirror():
    with session_ctx() as session:
        public, internal = _ogc_relations(session)

    missing = public - internal - PUBLIC_ONLY
    assert (
        not missing
    ), f"public ogc_* relations with no ogc_internal_ mirror: {sorted(missing)}"


def test_internal_only_relations_have_no_public_twin():
    with session_ctx() as session:
        public, _ = _ogc_relations(session)

    assert not (
        public & INTERNAL_ONLY
    ), f"internal-only layer published: {sorted(public & INTERNAL_ONLY)}"


def test_every_configured_edr_collection_has_both_views():
    with session_ctx() as session:
        public, internal = _ogc_relations(session)

    tables = {c["table"].removeprefix("ogc_") for c in EDR_COLLECTIONS}
    assert (
        tables <= public
    ), f"EDR collections with no public view: {sorted(tables - public)}"
    assert (
        tables <= internal
    ), f"EDR collections with no internal view: {sorted(tables - internal)}"
