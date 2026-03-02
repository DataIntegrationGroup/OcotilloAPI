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
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration


def run(session: Session) -> None:
    """
    Implement migration logic here.

    Use SQLAlchemy core for large batches:
      session.execute(insert(Model), rows)
    """
    return None


MIGRATION = DataMigration(
    id="YYYYMMDD_0000",
    alembic_revision="REVISION_ID",
    name="Short migration name",
    description="Why this data migration exists.",
    run=run,
    is_repeatable=False,
)
