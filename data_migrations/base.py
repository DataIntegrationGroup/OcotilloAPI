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
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DataMigration:
    id: str
    alembic_revision: str
    name: str
    description: str
    run: Callable[[Session], None]
    is_repeatable: bool = False
    # Optional read-only preview. Migrations that delete rows or re-point
    # foreign keys should provide one so the planned changes can be reviewed
    # before anything is written. It must not commit. Any return value is for
    # the caller's own use -- the runner ignores it.
    dry_run: Optional[Callable[[Session], object]] = None
