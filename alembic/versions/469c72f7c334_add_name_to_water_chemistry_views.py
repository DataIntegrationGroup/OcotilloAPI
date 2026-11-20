"""add a name column to the water-chemistry views

The EDR provider (core.edr_provider.StationEDRProvider) now reads a station's
name from a column called ``name`` in every backing view, the same column
ogc_manual_waterlevels publishes (7ae4753c9b3e). ogc_water_chemistry and
ogc_internal_water_chemistry carried the thing's name only as
``station_name``, so the water_chemistry EDR collection would fail on it.

This revision adds ``name`` (the thing's name) alongside ``station_name``.
``station_name`` stays: the chemistry API reads it through the
ChemistryResult ORM model (db/chemistry_views.py) and GET /chemistry/results.

Everything else -- the four-table union, release gating, id scheme, indexes
and comments -- is 3f9c1b7d2a64's, loaded from that file rather than copied,
so this revision cannot drift from it. Both views are materialized, so they
are dropped and rebuilt; the rebuild populates them, and the nightly pg_cron
refresh (x2y3z4a5b6c7) discovers them from the catalog as before.

Revision ID: 469c72f7c334
Revises: 7ae4753c9b3e
Create Date: 2026-11-18 00:00:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "469c72f7c334"
down_revision: Union[str, Sequence[str], None] = "7ae4753c9b3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PREVIOUS_REVISION = "3f9c1b7d2a64_chemistry_views_time_on_collection_date.py"

# The line in 3f9c1b7d2a64's SELECT that the new column goes after.
_STATION_NAME_LINE = "t.name                              AS station_name,"


def _load_previous_revision():
    """Import 3f9c1b7d2a64, the definition of record for these views."""
    path = Path(__file__).with_name(_PREVIOUS_REVISION)
    if not path.exists():
        raise RuntimeError(
            "Cannot rebuild the water-chemistry views: "
            f"{_PREVIOUS_REVISION} is missing from alembic/versions."
        )
    spec = importlib.util.spec_from_file_location("_chemistry_collection_date", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_water_chemistry_view_with_name(previous):
    """3f9c1b7d2a64's CREATE statement with ``name`` after ``station_name``."""

    def create(view_name: str, public_only: bool) -> str:
        sql = previous._create_water_chemistry_view(view_name, public_only)
        if sql.count(_STATION_NAME_LINE) != 1:
            # Fail the migration rather than build a view without the column.
            raise RuntimeError(
                f"Expected exactly one station_name column in {_PREVIOUS_REVISION}'s "
                f"{view_name} definition; cannot add name."
            )
        return sql.replace(
            _STATION_NAME_LINE,
            _STATION_NAME_LINE
            + "\n            t.name                              AS name,",
        )

    return create


def upgrade() -> None:
    previous = _load_previous_revision()
    previous._rebuild(
        _create_water_chemistry_view_with_name(previous),
        previous._create_indexes,
        previous.VIEW_COMMENTS,
    )


def downgrade() -> None:
    previous = _load_previous_revision()
    previous._rebuild(
        previous._create_water_chemistry_view,
        previous._create_indexes,
        previous.VIEW_COMMENTS,
    )
