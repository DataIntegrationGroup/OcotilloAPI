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
"""Publishing records the consent it implies.

`release_status='public'` and `publication_consent` were two axes with nothing
converting one into the other, which is why the legacy migration had to
grandfather everything. These cover the forward half: what publishing writes
from now on, so the two cannot drift again.
"""

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from db.destination import Destination
from db.engine import session_ctx
from db.publication_consent import PublicationConsent
from db.thing import Thing
from services.access_admin import register_destination
from services.publication import (
    PUBLICATION_DATA_TYPES,
    consent_for_public_thing,
    consent_on_publication,
)


@pytest.fixture
def destinations():
    with session_ctx() as session:
        for slug, name, kind in (
            ("public-web", "Public web", "public web"),
            ("ngwmn", "National Ground Water Monitoring Network", "harvester"),
        ):
            existing = session.execute(
                select(Destination).where(Destination.slug == slug)
            ).scalar_one_or_none()
            if existing is None:
                register_destination(
                    session, actor="tests", slug=slug, name=name, destination_kind=kind
                )
        session.commit()
    yield


@pytest.fixture
def thing_factory():
    created = []

    def _make(release_status):
        with session_ctx() as session:
            thing = Thing(
                name=f"CONSENT-{release_status}-{datetime.now().timestamp()}",
                thing_type="water well",
                release_status=release_status,
            )
            session.add(thing)
            session.commit()
            session.refresh(thing)
            created.append(thing.id)
            return thing.id

    yield _make

    with session_ctx() as session:
        session.execute(delete(Thing).where(Thing.id.in_(created)))
        session.commit()


def _consent_types(thing_id, slug):
    with session_ctx() as session:
        rows = session.execute(
            select(PublicationConsent.data_type)
            .join(Destination, Destination.id == PublicationConsent.destination_id)
            .where(
                PublicationConsent.thing_id == thing_id,
                Destination.slug == slug,
                PublicationConsent.revoked_at.is_(None),
            )
        ).scalars()
        return sorted(set(rows))


class TestConsentOnPublication:
    def test_it_writes_the_four_types_to_both_destinations(
        self, destinations, thing_factory
    ):
        thing_id = thing_factory("draft")
        with session_ctx() as session:
            consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()

        assert _consent_types(thing_id, "public-web") == sorted(PUBLICATION_DATA_TYPES)
        assert _consent_types(thing_id, "ngwmn") == sorted(PUBLICATION_DATA_TYPES)

    def test_it_does_not_publish_pii_or_field_operations(
        self, destinations, thing_factory
    ):
        """Those terms name material release_status never covered."""
        thing_id = thing_factory("draft")
        with session_ctx() as session:
            consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()

        written = _consent_types(thing_id, "public-web")
        assert "pii" not in written
        assert "field operations" not in written

    def test_it_is_idempotent(self, destinations, thing_factory):
        thing_id = thing_factory("draft")
        with session_ctx() as session:
            first = consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()
        with session_ctx() as session:
            second = consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()

        assert len(first) == len(PUBLICATION_DATA_TYPES) * 2
        assert second == []

    def test_it_does_not_resurrect_a_revoked_consent(self, destinations, thing_factory):
        """Re-publishing is not the moment to overturn somebody's revocation."""
        thing_id = thing_factory("draft")
        with session_ctx() as session:
            consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()

        with session_ctx() as session:
            session.execute(
                PublicationConsent.__table__.update()
                .where(
                    PublicationConsent.thing_id == thing_id,
                    PublicationConsent.data_type == "well construction",
                )
                .values(revoked_at=datetime.now(timezone.utc))
            )
            session.commit()

        with session_ctx() as session:
            consent_on_publication(session, actor="tests", thing_id=thing_id)
            session.commit()

        assert "well construction" not in _consent_types(thing_id, "public-web")


class TestConsentForPublicThing:
    def test_a_public_thing_gets_consent(self, destinations, thing_factory):
        thing_id = thing_factory("public")
        with session_ctx() as session:
            thing = session.get(Thing, thing_id)
            consent_for_public_thing(session, thing, {"name": "A Tester"})
            session.commit()

        assert _consent_types(thing_id, "public-web") == sorted(PUBLICATION_DATA_TYPES)

    def test_a_draft_thing_gets_nothing(self, destinations, thing_factory):
        thing_id = thing_factory("draft")
        with session_ctx() as session:
            thing = session.get(Thing, thing_id)
            assert consent_for_public_thing(session, thing, None) == []
            session.commit()

        assert _consent_types(thing_id, "public-web") == []

    def test_an_unregistered_destination_is_skipped_not_an_error(self, thing_factory):
        """Default deny: an environment that harvests nowhere publishes nothing."""
        thing_id = thing_factory("public")
        with session_ctx() as session:
            thing = session.get(Thing, thing_id)
            written = consent_on_publication(
                session,
                actor="tests",
                thing_id=thing.id,
                destinations=("no-such-destination",),
            )
            session.commit()
        assert written == []

    def test_consent_starts_today_so_it_is_live_immediately(
        self, destinations, thing_factory
    ):
        """A view compares starts_at <= current_date; tomorrow would publish nothing."""
        thing_id = thing_factory("public")
        with session_ctx() as session:
            thing = session.get(Thing, thing_id)
            written = consent_for_public_thing(session, thing, None)
            session.commit()
            assert all(row.starts_at <= date.today() for row in written)
