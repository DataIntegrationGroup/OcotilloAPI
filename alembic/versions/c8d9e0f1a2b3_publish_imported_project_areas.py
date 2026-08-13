"""publish imported project areas

Promotes every group carrying a project_area boundary from the untouched
"draft" default to release_status = 'public', so the boundaries imported from
the maps.nmt.edu Water_Resources layer reach the ogc_project_areas OGC layer.

Why this is needed: cli/project_area_import.py writes group.project_area but
never set release_status, so imported rows kept ReleaseMixin's "draft" default.
ogc_project_areas (see t6u7v8w9x0y1, re-created by f4a5b6c7d8e9) filters on
release_status = 'public', so the collection is published and advertised while
serving zero features.

Scope is deliberately narrow on two axes:

* Only rows with a non-null project_area. A group without geometry has nothing
  to contribute to the layer, and its release status is none of this
  migration's business.
* Only rows still at "draft". "private" and "archived" are deliberate curation
  decisions and must survive this migration; "provisional" and "public" need no
  change. Project areas are boundary polygons already published on
  maps.nmt.edu, so publishing the untouched default carries no disclosure risk.

group_type is deliberately NOT used to select rows. It is not provenance -- a
"Geographic Area" may itself be a legacy project -- so filtering on it would
both miss imported areas and catch rows this migration has no claim on.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-08-13 14:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLISH_SQL = """
    UPDATE "group"
    SET release_status = 'public'
    WHERE project_area IS NOT NULL
      AND release_status = 'draft'
"""


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "group" not in set(inspector.get_table_names(schema="public")):
        raise RuntimeError(
            "Cannot publish project areas. Missing required table: group"
        )

    result = bind.execute(text(PUBLISH_SQL))
    print(f"Published {result.rowcount} project area group(s) to the OGC layer.")


def downgrade() -> None:
    # Deliberately a no-op. Once applied, a published project area is
    # indistinguishable from one that was public before this ran, so reverting
    # would demote rows this migration never touched. Re-privatising a specific
    # group is an editorial action, not a schema rollback.
    pass
