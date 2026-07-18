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
from pathlib import Path

import pytest

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
