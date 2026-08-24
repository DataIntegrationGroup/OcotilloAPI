"""repair missing EDR water views

Recreates ogc_waterlevels / ogc_water_chemistry on any database whose
alembic_version claims z9a0b1c2d3e4 was applied while the views are in fact
absent.

Why this is needed: the CD run that first carried z9a0b1c2d3e4 to staging
failed in the Alembic step with "Multiple head revisions are present for given
argument 'head'". The revision graph was then repaired in-tree (eb89d046,
8ae9fe18), but the staging database came out the other side stamped past
z9a0b1c2d3e4 without its DDL ever having executed. Downstream revisions applied
normally, so nothing surfaced until an EDR query hit the missing relation:

    psycopg2.errors.UndefinedTable: relation "ogc_waterlevels" does not exist

Re-running z9a0b1c2d3e4 is not an option -- alembic_version already lists it,
and downgrading to it would tear out every revision since. This revision closes
the hole from the front of the chain instead.

The view SQL is imported from z9a0b1c2d3e4 rather than copied so the repaired
definition cannot drift from the definition of record.

Idempotent and safe on healthy databases: a view that is already present is
left untouched, so this is a no-op everywhere except the environments that
actually skipped the original revision.

Revision ID: b7c8d9e0f1a2
Revises: f3a1c2b4d5e6
Create Date: 2026-08-13 13:20:00.000000
"""

import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "f3a1c2b4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOURCE_REVISION = "z9a0b1c2d3e4_add_edr_water_views.py"


def _load_source_revision():
    # The view definitions live in z9a0b1c2d3e4. Importing them keeps this
    # repair honest: whatever that revision creates is exactly what a database
    # that skipped it gets back.
    path = Path(__file__).with_name(_SOURCE_REVISION)
    if not path.exists():
        raise RuntimeError(
            f"Cannot repair the EDR water views: {_SOURCE_REVISION} is missing "
            "from alembic/versions, so the view definitions of record are "
            "unavailable."
        )
    spec = importlib.util.spec_from_file_location("_edr_water_views", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEW_COMMENTS = {
    "ogc_waterlevels": (
        "Public depth-to-water readings (manual + transducer) for EDR."
    ),
    "ogc_water_chemistry": "Public water-chemistry analyses (by analyte) for EDR.",
}


def _relkind(view_name: str) -> str | None:
    bind = op.get_bind()
    return bind.execute(
        text("SELECT relkind FROM pg_class WHERE oid = to_regclass(:name)"),
        {"name": view_name},
    ).scalar()


def _check_required_tables(required_tables: set[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = set(inspector.get_table_names(schema="public"))
    missing = required_tables - existing
    if missing:
        raise RuntimeError(
            "Cannot repair the EDR water views. Missing required tables: "
            f"{sorted(missing)}"
        )


def _repair_view(view_name: str, create_sql: str) -> None:
    relkind = _relkind(view_name)
    if relkind == "v":
        # Already present and the right kind -- the database applied
        # z9a0b1c2d3e4 for real. Leave it alone rather than churning DDL that
        # other objects may depend on.
        return
    if relkind is not None:
        # Present as something other than a plain view (materialized view,
        # table). That is not a state z9a0b1c2d3e4 or its downstream revisions
        # produce, so fail loudly instead of silently replacing it.
        raise RuntimeError(
            f"Cannot repair {view_name}: it already exists with relkind "
            f"{relkind!r}, not a plain view. Inspect it by hand before "
            "re-running this migration."
        )

    op.execute(text(create_sql))
    op.execute(text(f"COMMENT ON VIEW {view_name} IS '{VIEW_COMMENTS[view_name]}'"))


def upgrade() -> None:
    source = _load_source_revision()
    _check_required_tables(set(source.REQUIRED_TABLES))

    _repair_view("ogc_waterlevels", source._create_waterlevels_view())
    _repair_view("ogc_water_chemistry", source._create_water_chemistry_view())


def downgrade() -> None:
    # Deliberately a no-op. These views belong to z9a0b1c2d3e4; dropping them
    # here would break EDR on every database that applied that revision
    # correctly. Downgrading past z9a0b1c2d3e4 removes them.
    pass
