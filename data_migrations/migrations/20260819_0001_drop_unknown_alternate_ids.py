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
Remove the unattributed `Unknown` alternate identifiers from the San Acacia
Reach wells that the automated ingestion pipeline reads.

Each of these wells carries two identifier links: an `NMBGMR` one and an
`Unknown` one with no recorded provenance. For most wells they agree, and the
`Unknown` row is redundant. For some they contradict each other -- `SO-0131`
carries NMBGMR `BRN-E04B (shallow)` and Unknown `BRN-E04A`, while `SO-0132` has
them the other way round, so the two sources disagree about which physical well
is which (BDMS-1168).

Removing the unattributed rows leaves NMBGMR as the single answer. That is the
point: an identifier nobody can source is worse than no identifier, because it
looks like corroboration.

Scoped to the 38 wells this pipeline ingests, deliberately. The wider reach
network has 152 such links and every `SO-` well has 263 between them; widening
this is a separate decision, and 19 of the reach network's links are the
conflicting ones BDMS-1168 is tracking -- deleting those would remove the
evidence of the conflict along with the conflict.

Wells are matched by name rather than by id so the migration means the same
thing in every environment.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.thing import Thing, ThingIdLink

UNATTRIBUTED = "Unknown"

WELL_NAMES = (
    "SO-0125",
    "SO-0131",
    "SO-0140",
    "SO-0142",
    "SO-0144",
    "SO-0145",
    "SO-0146",
    "SO-0148",
    "SO-0160",
    "SO-0163",
    "SO-0165",
    "SO-0166",
    "SO-0167",
    "SO-0170",
    "SO-0175",
    "SO-0177",
    "SO-0189",
    "SO-0190",
    "SO-0191",
    "SO-0194",
    "SO-0200",
    "SO-0204",
    "SO-0213",
    "SO-0215",
    "SO-0219",
    "SO-0221",
    "SO-0223",
    "SO-0224",
    "SO-0226",
    "SO-0234",
    "SO-0236",
    "SO-0238",
    "SO-0245",
    "SO-0246",
    "SO-0247",
    "SO-0249",
    "SO-0250",
    "SO-0261",
)


def run(session: Session) -> None:
    """Delete the unattributed links, leaving every other organization alone."""
    thing_ids = session.scalars(
        select(Thing.id).where(Thing.name.in_(WELL_NAMES))
    ).all()

    missing = len(WELL_NAMES) - len(thing_ids)
    if missing:
        # Not fatal -- a database without these wells is a database this
        # migration has nothing to do in -- but silence would hide a rename.
        print(
            f"  {missing} of {len(WELL_NAMES)} wells not found by name; "
            "skipping those."
        )

    if not thing_ids:
        return None

    result = session.execute(
        delete(ThingIdLink).where(
            ThingIdLink.thing_id.in_(thing_ids),
            ThingIdLink.alternate_organization == UNATTRIBUTED,
        )
    )
    print(
        f"  removed {result.rowcount} {UNATTRIBUTED!r} links from {len(thing_ids)} wells"
    )
    return None


MIGRATION = DataMigration(
    id="20260819_0001_drop_unknown_alternate_ids",
    alembic_revision="b2c3d4e5f6a7",
    name="Drop unattributed alternate IDs from San Acacia Reach wells",
    description=(
        "Each ingested San Acacia well carries an NMBGMR identifier and an "
        "unattributed 'Unknown' one. They mostly duplicate, and sometimes "
        "contradict -- SO-0131 and SO-0132 disagree about which is BRN-E04A "
        "(BDMS-1168). Removing the unattributed rows leaves one answer."
    ),
    run=run,
    is_repeatable=False,
)


# ============= EOF =============================================
