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
The access-control tables start empty, and empty means default deny (ADR5).
This writes down the access that already exists, so switching the layer on
changes nobody's day:

1. **Role grants.** ``services/access_seed.py``, the day-one baseline from
   ADR5 5.2: one global grant per Authentik role, capability and access data
   type, plus one per role and UI surface.
2. **Landowner consent for what is already public.** Every thing carrying
   ``release_status='public'`` gets a consent row per access data type against
   each baseline destination -- the anonymous public web and NGWMN -- which is
   the grandfathering half of PUB-D13. Both get the same rows because
   ``release_status`` never distinguished them: a public well was in the OGC
   collections and in what NGWMN harvests, and there was no way to say yes to
   one and no to the other. There is now, and it is a revocation.

The seeder is called rather than copied. Its mapping is the one the CLI shows
in ``oco seed-access-grants``, and two copies of a security baseline is how the
two drift.

## Why the consent half is a migration and not a screen

Publication today is a ``release_status`` column, set in bulk. Consent rows are
per (thing, destination, data type). Nothing converts one into the other, so
until something does, turning consent on would unpublish every well the public
can see today. This is that conversion, and it is deliberately the *widest*
reading of the existing state: a public well is grandfathered for all four data
types, because that is what ``release_status='public'`` already means.

ADR5 leaves the choice between grandfathering and re-consenting to the data
owner, and this takes the grandfathering branch. Re-consenting per data type
happens by revoking these rows through the console, which is the part of the
model that makes a narrower answer expressible at all.

Nothing here reads the grant tables back, so running it changes no behaviour on
its own -- no endpoint consults the visibility layer yet.

Idempotent both halves: the seeder skips what it has written before (including
what somebody has since revoked, which stays revoked), and the consent half
skips any (thing, data type) that already has a live row for this destination.
"""

from dataclasses import dataclass
from datetime import date, timezone, datetime

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from data_migrations.base import DataMigration
from db.authorization_audit import AuthorizationAudit, CONSENT_RECORDED
from db.destination import Destination
from db.lexicon import LexiconTerm
from db.publication_consent import PublicationConsent
from db.thing import Thing
from domain.access import CAPABILITY_VIEW, PRINCIPAL_ROLE, SCOPE_GLOBAL
from services.access_admin import register_destination
from services.access_seed import (
    ROLE_BASELINE,
    SURFACE_BASELINE,
    data_types,
    seed_role_grants,
)
from transfers.logger import logger


@dataclass(frozen=True)
class BaselineDestination:
    """A destination this migration expects to exist, and registers if not.

    ``excluded_data_types`` names what this destination is *not* consented to
    receive. It is a subtraction rather than a list of what it does get,
    because the grandfathering claim is "whatever public already meant, minus
    what this destination was never offered" -- and writing it as a subtraction
    means a data type added to the lexicon next year is covered by the same
    reasoning instead of being silently dropped from one destination and not
    the other.
    """

    slug: str
    name: str
    kind: str
    description: str
    excluded_data_types: tuple = ()


# The destinations the legacy data is already offered to. Both receive the
# same grandfathered consent, because `release_status='public'` did not
# distinguish between them: a public well is in the OGC collections and in
# what NGWMN harvests.
#
# The kinds differ, and that is what makes them different destinations rather
# than one: `core/field-allowlists.yml` keys audiences by kind, so the public
# web gets kilometre-rounded coordinates and a harvester gets ten-metre ones.
PUBLIC_DESTINATION = BaselineDestination(
    slug="public-web",
    name="Public web",
    kind="public web",
    description=(
        "Anonymous access to the public OGC collections and the public API. "
        "The destination every unauthenticated caller is."
    ),
)
NGWMN_DESTINATION = BaselineDestination(
    slug="ngwmn",
    name="National Ground Water Monitoring Network",
    kind="harvester",
    description=(
        "The USGS-run federal network that harvests well records and water "
        "levels on a schedule. Harvested copies live in someone else's "
        "system, so withdrawing consent stops the offering and does not "
        "recall what was already taken (ADR5, 3.6)."
    ),
    # Water chemistry is not part of what NGWMN is offered. Grandfathering it
    # would hand a federal harvester a data type nobody agreed to send it, and
    # the whole point of the per-data-type model is that this is expressible.
    excluded_data_types=("water chemistry",),
)
BASELINE_DESTINATIONS = (PUBLIC_DESTINATION, NGWMN_DESTINATION)

# Kept as a module constant because the lexicon guard and the tests name it.
PUBLIC_DESTINATION_SLUG = PUBLIC_DESTINATION.slug
PUBLIC_DESTINATION_KIND = PUBLIC_DESTINATION.kind

# Recorded as having captured the consent. Not a person on purpose: nobody
# made a phone call for these. They exist because the record was already
# public, and the log should say so rather than name someone who did not
# decide it.
GRANDFATHER_ACTOR = "system:legacy-grandfather"
GRANDFATHER_NOTES = (
    "Grandfathered from release_status='public' (ADR5, PUB-D13). Not a "
    "consent anyone gave in these terms: it records that this well's data was "
    "already published before consent was tracked per data type. Narrowing it "
    "is a revocation somebody makes deliberately."
)

# The level that means the record is offered to anonymous callers today. The
# other levels in the release_status lexicon are not published, and the review
# states in there (`provisional`, `final`) are the historical rows the split
# to `data_maturity` has not moved yet -- neither of which is consent to
# publish.
PUBLIC_RELEASE_STATUS = "public"


def _require_lexicon_terms(session: Session, terms: tuple) -> None:
    """Fail before writing rather than on a foreign key deep into a batch.

    Both grant subjects and the data type on a consent row are lexicon terms.
    An environment whose lexicon has not been seeded cannot hold these rows,
    and the useful error names the command that fixes it.
    """
    present = set(
        session.execute(
            select(LexiconTerm.term).where(LexiconTerm.term.in_(terms))
        ).scalars()
    )
    missing = sorted(set(terms) - present)
    if missing:
        raise RuntimeError(
            f"lexicon terms missing: {', '.join(missing)}. "
            "Run `oco initialize-lexicon` before this migration."
        )


class DestinationKindConflict(RuntimeError):
    """A registered destination has a different kind than the baseline expects."""


def _destination(session: Session, spec: BaselineDestination) -> Destination:
    """The registry row for this destination, registered if it is missing.

    A row that already exists under this slug is used as it stands -- never
    edited. If its kind disagrees this refuses rather than continuing, because
    the kind is what picks the field allowlist: writing consent against a
    destination whose kind says "public web" when the baseline meant
    "harvester" would publish a different set of fields than the operator
    intended, in whichever direction. Somebody decides that, not this script.
    """
    destination = session.execute(
        select(Destination).where(Destination.slug == spec.slug)
    ).scalar_one_or_none()
    if destination is not None:
        if destination.destination_kind != spec.kind:
            raise DestinationKindConflict(
                f"destination '{spec.slug}' is registered as "
                f"'{destination.destination_kind}', and this baseline expects "
                f"'{spec.kind}'. The kind selects the field allowlist in "
                "core/field-allowlists.yml, so fix the registry row (or the "
                "baseline) rather than publishing under the wrong one."
            )
        return destination

    return register_destination(
        session,
        GRANDFATHER_ACTOR,
        slug=spec.slug,
        name=spec.name,
        destination_kind=spec.kind,
        description=spec.description,
    )


def _existing_consent(session: Session, destination_id: int) -> set:
    """(thing, data type) pairs this destination already has a live row for.

    Revoked rows are not here: the unique index only covers live ones, and a
    consent somebody withdrew is not re-recorded by running this again.
    """
    rows = session.execute(
        select(PublicationConsent.thing_id, PublicationConsent.data_type).where(
            PublicationConsent.destination_id == destination_id,
            PublicationConsent.revoked_at.is_(None),
        )
    ).all()
    return {(thing_id, data_type) for thing_id, data_type in rows}


def consented_data_types(spec: BaselineDestination) -> tuple:
    """The data types this destination is grandfathered for."""
    return tuple(
        data_type
        for data_type in data_types()
        if data_type not in spec.excluded_data_types
    )


def _public_thing_ids(session: Session) -> list:
    return list(
        session.execute(
            select(Thing.id).where(Thing.release_status == PUBLIC_RELEASE_STATUS)
        ).scalars()
    )


def _grandfather_public_things(
    session: Session,
    spec: BaselineDestination = PUBLIC_DESTINATION,
    public_thing_ids: list = None,
) -> int:
    """One consent row per (public thing, data type). Returns rows written."""
    destination = _destination(session, spec)
    already = _existing_consent(session, destination.id)

    if public_thing_ids is None:
        public_thing_ids = _public_thing_ids(session)
        logger.info(
            f"{len(public_thing_ids)} thing(s) are release_status="
            f"'{PUBLIC_RELEASE_STATUS}'."
        )

    starts_at = date.today()
    rows = [
        {
            "thing_id": thing_id,
            "destination_id": destination.id,
            "data_type": data_type,
            # NULL: the decision was institutional, not a landowner's. The
            # model allows this precisely so grandfathered rows do not have to
            # invent a consenting contact.
            "contact_id": None,
            "recorded_by": GRANDFATHER_ACTOR,
            "notes": GRANDFATHER_NOTES,
            "starts_at": starts_at,
            "ends_at": None,
        }
        for thing_id in public_thing_ids
        for data_type in consented_data_types(spec)
        if (thing_id, data_type) not in already
    ]
    if not rows:
        return 0

    # Core insert rather than record_consent(): that commits per row and this
    # is one transaction over tens of thousands of them. The audit rows are
    # written here instead, from what the insert returns, so the promise that
    # no consent lands without a trace still holds.
    written = session.execute(
        insert(PublicationConsent).returning(
            PublicationConsent.id,
            PublicationConsent.thing_id,
            PublicationConsent.data_type,
        ),
        rows,
    ).all()

    recorded_at = datetime.now(tz=timezone.utc)
    session.execute(
        insert(AuthorizationAudit),
        [
            {
                "event_type": CONSENT_RECORDED,
                "actor": GRANDFATHER_ACTOR,
                "subject_table": PublicationConsent.__tablename__,
                "subject_id": consent_id,
                "created_at": recorded_at,
                "detail": {
                    "thing_id": thing_id,
                    "destination_id": destination.id,
                    "data_type": data_type,
                    "contact_id": None,
                    "starts_at": starts_at.isoformat(),
                    "ends_at": None,
                    "grandfathered_from": PUBLIC_RELEASE_STATUS,
                },
            }
            for consent_id, thing_id, data_type in written
        ],
    )
    session.commit()
    return len(written)


def _required_terms() -> tuple:
    """Every controlled term this migration writes into a lexicon-backed column.

    Capability, scope type, principal type, data type, UI surface and
    destination kind are all foreign keys to ``lexicon_term.term``. Checking
    them together means an unseeded environment fails on the first statement
    with a list, rather than partway through a batch with a constraint name.
    """
    capabilities = {
        capability
        for capabilities in ROLE_BASELINE.values()
        for capability in capabilities
    } | {CAPABILITY_VIEW}
    surfaces = {
        surface for surfaces in SURFACE_BASELINE.values() for surface in surfaces
    }
    return tuple(
        sorted(
            set(data_types())
            | capabilities
            | surfaces
            | {spec.kind for spec in BASELINE_DESTINATIONS}
            | {PRINCIPAL_ROLE, SCOPE_GLOBAL}
        )
    )


def run(session: Session) -> None:
    _require_lexicon_terms(session, _required_terms())

    plan = seed_role_grants(session, apply=True)
    logger.info(
        f"Baseline grants: created {len(plan.created)}, "
        f"left {len(plan.skipped)} alone."
    )

    public_thing_ids = _public_thing_ids(session)
    logger.info(
        f"{len(public_thing_ids)} thing(s) are release_status="
        f"'{PUBLIC_RELEASE_STATUS}'."
    )
    for spec in BASELINE_DESTINATIONS:
        written = _grandfather_public_things(session, spec, public_thing_ids)
        logger.info(
            f"Grandfathered {written} consent row(s) for {spec.slug} "
            f"({', '.join(consented_data_types(spec))})."
        )
        if spec.excluded_data_types:
            logger.info(
                f"  {spec.slug} is not consented for: "
                f"{', '.join(spec.excluded_data_types)}."
            )

    total = session.execute(
        select(func.count()).select_from(PublicationConsent)
    ).scalar_one()
    logger.info(f"{total} publication consent row(s) now exist.")


MIGRATION = DataMigration(
    id="20260829_0001_seed_legacy_access_grants",
    alembic_revision="a396d7d9928d",
    name="Seed the legacy access baseline",
    description=(
        "Writes down the access that already exists so the ADR5 layer can be "
        "switched on without changing anyone's day: the day-one role baseline "
        "(data types and UI surfaces) from services/access_seed.py, and one "
        "publication consent row per (release_status='public' thing, access "
        "data type) against the public-web destination, grandfathering "
        "PUB-D13."
    ),
    run=run,
    is_repeatable=False,
)

# ============= EOF =============================================
