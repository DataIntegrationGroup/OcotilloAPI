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
"""Scope the project_areas OGC views to the Aquifer Mapping Study Areas layer.

Both ``ogc_project_areas`` (public) and ``ogc_internal_project_areas`` used to
serve every group that carried a ``project_area`` polygon. That set had drifted
past the ArcGIS "Aquifer Mapping Study Areas" layer (MapServer layer 18): older
boundaries under legacy names lingered in the layer while some current study
areas sat unpublished.

These views now serve only the groups that belong to the layer, identified
structurally as the children of the container group named
``Aquifer Mapping Study Areas``. The membership is set by the data migration
``20260905_0001_parent_project_areas_under_layer18``, which creates that parent
and re-points every layer-18 owner group's ``parent_group_id`` at it. The parent
is matched by name rather than id so the same view definition is correct in
every environment.

Ordering note: applied by CD before that data migration runs (data migrations
have no CD path), these views return zero rows until the parent group exists and
its children are re-pointed. That is deliberate -- an empty layer, never a wrong
one. Run the data migration in each environment to populate it.
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "c5d6e7f8a9b0"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

PARENT_GROUP_NAME = "Aquifer Mapping Study Areas"

# Column list is identical to the pre-existing views; only the FROM/WHERE change.
_COLUMNS = """
            g.id,
            g.name,
            g.description,
            g.group_type,
            g.release_status,
            g.project_area
"""


def _create_layer18_view(view_name: str, public_only: bool) -> str:
    release_filter = " AND g.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {view_name} AS
        SELECT
            {_COLUMNS.strip()}
        FROM "group" AS g
        JOIN "group" AS parent ON g.parent_group_id = parent.id
        WHERE parent.name = '{PARENT_GROUP_NAME}'
          AND g.project_area IS NOT NULL{release_filter}
    """


def _create_all_areas_view(view_name: str, public_only: bool) -> str:
    """The pre-migration definition: every group carrying a polygon."""
    release_filter = " AND release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {view_name} AS
        SELECT
            id,
            name,
            description,
            group_type,
            release_status,
            project_area
        FROM "group" AS g
        WHERE project_area IS NOT NULL{release_filter}
    """


def upgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS ogc_project_areas"))
    op.execute(text("DROP VIEW IF EXISTS ogc_internal_project_areas"))
    op.execute(text(_create_layer18_view("ogc_project_areas", public_only=True)))
    op.execute(
        text(_create_layer18_view("ogc_internal_project_areas", public_only=False))
    )


def downgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS ogc_project_areas"))
    op.execute(text("DROP VIEW IF EXISTS ogc_internal_project_areas"))
    op.execute(text(_create_all_areas_view("ogc_project_areas", public_only=True)))
    op.execute(
        text(_create_all_areas_view("ogc_internal_project_areas", public_only=False))
    )
