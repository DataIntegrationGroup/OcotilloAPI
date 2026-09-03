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
services/publication.py

Publishing a thing, in the sense the public collections now mean it.

`release_status = 'public'` used to be the whole of publication. Since
c5d6e7f8a9b0 and d6e7f8a9b0c1 the public-web and ngwmn relations read
`publication_consent` as well, so a thing marked public with no consent rows
publishes a row of nulls -- or, on the NGWMN views, nothing at all.

The data migration `20260829_0001_seed_legacy_access_grants` grandfathered
everything public on the day it ran. This is the forward half of the same
sentence: what publishing writes from now on, so the two axes cannot drift
again.

**Which types a bare publish grants.** The same four the grandfathering used:
site metadata, well construction, water level, water chemistry -- the widest
reading of what `release_status='public'` already meant. Deliberately not
`pii` or `field operations`: those terms exist to name material that was never
covered by that column, and inheriting them here would publish landowner
contacts and gate codes on the strength of a checkbox nobody ticked for them.

Narrowing from the four is a revocation, made per thing and per destination in
the console. This function will not re-grant what somebody revoked -- it skips
any (thing, destination, data type) that already has a row, live or revoked,
for the same reason the grant seeder does.
"""

from datetime import date

from sqlalchemy import select

from db.destination import Destination
from db.publication_consent import PublicationConsent
from services.access_admin import record_consent

# What `release_status='public'` has always meant, made explicit.
PUBLICATION_DATA_TYPES = (
    "site metadata",
    "well construction",
    "water level",
    "water chemistry",
)

# Destinations a bare publish reaches. Both were registered by the legacy seed.
PUBLICATION_DESTINATIONS = ("public-web", "ngwmn")


def _existing_pairs(session, thing_id: int) -> set:
    """(destination_id, data_type) this thing already has a row for.

    Revoked rows count. A revocation is somebody's decision, and re-publishing
    is not the moment to overturn it silently.
    """
    rows = session.execute(
        select(PublicationConsent.destination_id, PublicationConsent.data_type).where(
            PublicationConsent.thing_id == thing_id
        )
    ).all()
    return {(destination_id, data_type) for destination_id, data_type in rows}


def consent_on_publication(
    session,
    actor: str,
    thing_id: int,
    starts_at: date = None,
    destinations=PUBLICATION_DESTINATIONS,
    data_types=PUBLICATION_DATA_TYPES,
) -> list:
    """Record the consent that publishing a thing implies.

    Idempotent, and it will not resurrect a revoked row. Returns what it
    wrote, which is empty on the second call.
    """
    starts_at = starts_at or date.today()
    existing = _existing_pairs(session, thing_id)

    written = []
    for slug in destinations:
        destination = session.execute(
            select(Destination).where(Destination.slug == slug)
        ).scalar_one_or_none()
        if destination is None or not destination.active:
            # A destination nobody registered here is not an error: an
            # environment that does not harvest to NGWMN simply has no row.
            continue

        for data_type in data_types:
            if (destination.id, data_type) in existing:
                continue
            written.append(
                record_consent(
                    session,
                    actor=actor,
                    thing_id=thing_id,
                    destination_id=destination.id,
                    data_type=data_type,
                    starts_at=starts_at,
                    notes="Recorded on publication.",
                )
            )
    return written


# ============= EOF =============================================
