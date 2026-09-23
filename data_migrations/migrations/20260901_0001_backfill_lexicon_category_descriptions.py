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
"""
Backfill `lexicon_category.description` from `core/lexicon.json`.

61 of the 62 seeded categories carried `description = NULL`; only
`data_maturity` had one. Descriptions for the rest were written into
`core/lexicon.json`, but `core.initializers.init_lexicon` inserted categories
and skipped the ones already present, so a database seeded before the
descriptions existed never received them. Staging and production are both in
that state.

`init_lexicon` now upserts the description instead, so a fresh seed and a
re-run of `oco initialize-lexicon` both carry the text. This migration exists
because neither happens on deploy -- CD runs alembic only, and re-seeding a
populated database is a heavier operation than setting one column.

No alembic revision accompanies this; `lexicon_category.description` has
existed since the initial migration, which is what `alembic_revision` names
below. The change is data, not schema.

Only rows whose description IS NULL are written. Re-running is a no-op, and a
description edited through `/lexicon` is left alone rather than reset to the
seed text -- the same rule `init_lexicon` applies. Categories present in the
database but absent from the JSON are untouched.
"""

import json
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.lexicon import LexiconCategory

LEXICON_PATH = Path(__file__).resolve().parents[2] / "core" / "lexicon.json"


def _seed_descriptions() -> dict[str, str]:
    """Category name -> description, for the categories that have one."""
    with open(LEXICON_PATH) as f:
        lexicon = json.load(f)
    return {
        category["name"]: category["description"]
        for category in lexicon["categories"]
        if category.get("description")
    }


def run(session: Session) -> None:
    """Set a description on every category that has none."""
    descriptions = _seed_descriptions()
    updated = 0
    for name, description in descriptions.items():
        result = session.execute(
            update(LexiconCategory)
            .where(
                LexiconCategory.name == name,
                LexiconCategory.description.is_(None),
            )
            .values(description=description)
            .execution_options(synchronize_session=False)
        )
        updated += result.rowcount
    print(
        f"  set description on {updated} lexicon categories "
        f"({len(descriptions)} available in core/lexicon.json)"
    )
    return None


MIGRATION = DataMigration(
    id="20260901_0001_backfill_lexicon_category_descriptions",
    alembic_revision="66ac1af4ba69",
    name="Backfill lexicon category descriptions",
    description=(
        "61 of 62 lexicon categories were seeded with description = NULL "
        "before the descriptions were written into core/lexicon.json. "
        "init_lexicon only inserted missing categories, so existing databases "
        "never got them. Sets the description on categories that still have "
        "none; leaves edited descriptions alone."
    ),
    run=run,
    is_repeatable=False,
)


# ============= EOF =============================================
