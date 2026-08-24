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
from sqlalchemy import update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.group import Group


def run(session: Session) -> None:
    session.execute(
        update(Group)
        .where(Group.project_area.isnot(None))
        .values(release_status="public")
    )
    session.commit()


MIGRATION = DataMigration(
    id="20260714_0001_publish_project_areas",
    alembic_revision="f4a5b6c7d8e9",
    name="Publish all project_areas records",
    description=(
        "Marks every group record backing the project_areas OGC layer "
        "(project_area IS NOT NULL) as release_status='public'. Confirmed "
        "via docs/ogc-layer-audit.md that all 56 current rows are "
        "release_status='draft'."
    ),
    run=run,
    is_repeatable=False,
)
