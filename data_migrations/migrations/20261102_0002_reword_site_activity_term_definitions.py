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
Reword the definitions of the three `site_activity` terms.

The terms Water Level Sample, Water Chemistry Sample and Datalogger
Installation were defined as "Permissions for ...", which after 652b0abb3241
is the wrong word: they name what an owner consents to, and "permission" now
means what staff may do. "Permissions for water taking chemistry samples" also
had its words out of order.

`core/lexicon.json` carries the new text for a fresh seed, but
`core.initializers.init_lexicon` inserts only missing terms and never updates
an existing definition, and CD runs alembic only, so existing databases need
this.

A definition is rewritten only while it still holds the old seed text. One
edited through `/lexicon` is left alone, the rule the category description
backfill (20260901_0001) follows. Re-running finds nothing to change.
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.lexicon import LexiconTerm

# term -> (old seed definition, new definition)
DEFINITIONS = {
    "Water Level Sample": (
        "Permissions for taking water level samples",
        "Owner consent to measure water levels at the site",
    ),
    "Water Chemistry Sample": (
        "Permissions for water taking chemistry samples",
        "Owner consent to collect water chemistry samples at the site",
    ),
    "Datalogger Installation": (
        "Permissions for installing dataloggers",
        "Owner consent to install a datalogger at the site",
    ),
}


def run(session: Session) -> None:
    """Rewrite each definition that still holds its old seed text."""
    updated = 0
    for term, (old, new) in DEFINITIONS.items():
        result = session.execute(
            update(LexiconTerm)
            .where(LexiconTerm.term == term, LexiconTerm.definition == old)
            .values(definition=new)
            .execution_options(synchronize_session=False)
        )
        updated += result.rowcount
    print(f"  reworded {updated} of {len(DEFINITIONS)} site_activity definitions")
    return None


MIGRATION = DataMigration(
    id="20261102_0002_reword_site_activity_term_definitions",
    alembic_revision="652b0abb3241",
    name="Reword site_activity term definitions",
    description=(
        "The three site_activity terms were defined as 'Permissions for ...'. "
        "Rewrites each definition to describe owner consent, only where it "
        "still holds the old seed text; edited definitions are left alone."
    ),
    run=run,
    is_repeatable=False,
)
