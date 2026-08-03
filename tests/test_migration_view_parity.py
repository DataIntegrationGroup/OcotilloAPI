"""Drift detection between the public (A1) and internal (A11) OGC migrations.

The two chemistry pivot views (major/minor) are dominated by long
analyte-alias CASE-mapping blocks that encode real lab-data business
knowledge. Because this codebase keeps Alembic migrations self-contained
with no cross-migration imports, that logic is duplicated rather than
shared between f4a5b6c7d8e9 (public) and 2d3c3a268652 (internal). If someone
fixes an analyte mapping in one file without the other, the public and
internal chemistry layers silently diverge -- this test turns that into a
loud, specific CI failure instead.
"""

import ast
import re
from pathlib import Path

import pytest

VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
PUBLIC_MIGRATION = (
    VERSIONS_DIR / "f4a5b6c7d8e9_apply_public_release_status_filter_to_ogc_views.py"
)
INTERNAL_MIGRATION = VERSIONS_DIR / "2d3c3a268652_create_internal_ogc_views.py"
EDR_MIGRATION = VERSIONS_DIR / "z9a0b1c2d3e4_add_edr_water_views.py"

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


# ---------------------------------------------------------------------------
# Forward-looking coverage check: does every public ogc_* relation (across
# f4a5b6c7d8e9 and any later migration that adds more, like z9a0b1c2d3e4's
# EDR views) have an ogc_internal_ mirror? This is exactly the gap that let
# the EDR views land on staging with no internal counterpart in the first
# place -- nothing caught it until a human noticed.
# ---------------------------------------------------------------------------

# Matches "CREATE VIEW ogc_x AS" / "CREATE MATERIALIZED VIEW ogc_internal_x
# AS" for any *literal* relation name. Deliberately does not match the 11
# thing-type views on either side of the parity: their names are built from
# an f-string variable (ogc_{safe_view_id}), not a literal, in both files --
# handled separately via THING_VIEWS below.
_CREATE_VIEW_RE = re.compile(
    r"CREATE (?:MATERIALIZED )?VIEW (ogc_(?:internal_)?[A-Za-z0-9_]+) AS"
)


def _literal_view_names(path: Path) -> set[str]:
    return set(_CREATE_VIEW_RE.findall(path.read_text(encoding="utf-8")))


def _thing_view_ids(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "THING_VIEWS" in targets and isinstance(node.value, ast.List):
                return {
                    elt.elts[0].value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Tuple)
                }
    raise AssertionError(f"THING_VIEWS not found in {path}")


def test_internal_migration_mirrors_every_public_relation():
    public_thing_ids = _thing_view_ids(PUBLIC_MIGRATION)
    internal_thing_ids = _thing_view_ids(INTERNAL_MIGRATION)
    assert public_thing_ids == internal_thing_ids, (
        f"THING_VIEWS has drifted: public has {public_thing_ids}, "
        f"internal has {internal_thing_ids}"
    )

    public_relation_ids = {
        name.removeprefix("ogc_")
        for name in _literal_view_names(PUBLIC_MIGRATION)
        | _literal_view_names(EDR_MIGRATION)
    } | public_thing_ids
    internal_relation_ids = {
        name.removeprefix("ogc_internal_")
        for name in _literal_view_names(INTERNAL_MIGRATION)
    } | internal_thing_ids

    missing = public_relation_ids - internal_relation_ids
    assert not missing, (
        "public ogc_* relations with no ogc_internal_ mirror in "
        f"{INTERNAL_MIGRATION.name}: {sorted(missing)}"
    )
    assert len(public_relation_ids) == 24, (
        "expected 24 total relations (11 thing-type + 11 from f4a5b6c7d8e9 + "
        f"2 EDR from z9a0b1c2d3e4), got {len(public_relation_ids)}: "
        f"{sorted(public_relation_ids)}"
    )
