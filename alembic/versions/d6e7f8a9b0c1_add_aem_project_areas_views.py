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
"""Add the AEM project-areas OGC views.

The airborne electromagnetic (AEM) study areas in the "Aquifer Mapping Study
Areas" layer get their own OGC layer, separate from the general project areas.
Like ``ogc_project_areas``, membership is structural: the children of the
container group named ``AEM Project Areas``, which the data migration
``20260905_0002_parent_aem_project_areas`` creates and populates.

Creates ``ogc_aem_project_areas`` (public) and ``ogc_internal_aem_project_areas``
(internal). Registered as the ``aem_project_areas`` collection in
``core/pygeoapi-config.yml`` and ``core/pygeoapi-config-internal.yml``.

Ordering note: as with the sibling migration, these views return zero rows until
the data migration creates the parent and re-points its children. An empty
layer, never a wrong one.
"""

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None

PARENT_GROUP_NAME = "AEM Project Areas"


def _create_aem_view(view_name: str, public_only: bool) -> str:
    release_filter = " AND g.release_status = 'public'" if public_only else ""
    return f"""
        CREATE VIEW {view_name} AS
        SELECT
            g.id,
            g.name,
            g.description,
            g.group_type,
            g.release_status,
            g.project_area
        FROM "group" AS g
        JOIN "group" AS parent ON g.parent_group_id = parent.id
        WHERE parent.name = '{PARENT_GROUP_NAME}'
          AND g.project_area IS NOT NULL{release_filter}
    """


def upgrade() -> None:
    op.execute(text(_create_aem_view("ogc_aem_project_areas", public_only=True)))
    op.execute(
        text(_create_aem_view("ogc_internal_aem_project_areas", public_only=False))
    )


def downgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS ogc_aem_project_areas"))
    op.execute(text("DROP VIEW IF EXISTS ogc_internal_aem_project_areas"))
