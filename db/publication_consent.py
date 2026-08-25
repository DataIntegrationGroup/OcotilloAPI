# ===============================================================================
# Copyright 2025 ross
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
db/publication_consent.py

The landowner's half of ADR5: did the owner of this well agree to publish this
data type to this destination?

Kept apart from ``db/permission_grant.py`` on purpose. Both reduce to the same
grammar and both are evaluated by ``services/visibility.py``, but they are
decided by different people on different authority and revoked by different
events -- a phone call here, an HR-shaped event there. One engine, two tables.

An owner willing to share water levels but not chemistry is one row, not a
workaround.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, AutoBaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.contact import Contact
    from db.destination import Destination
    from db.thing import Thing


class PublicationConsent(Base, AutoBaseMixin):
    """One consent: this thing's data type is offered to this destination."""

    # --- What is published, and where ---
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    destination_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("destination.id"), nullable=False
    )
    data_type: Mapped[str] = lexicon_term(nullable=False)

    # --- Who agreed ---
    # Nullable because the Bureau owns some of the wells it monitors, and
    # inventing a consenting contact for those would be a lie. NULL means the
    # decision was institutional; `recorded_by` still says who made it.
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=True
    )
    recorded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- When ---
    starts_at: Mapped[date] = mapped_column(nullable=False)
    ends_at: Mapped[Optional[date]] = mapped_column(nullable=True)

    # --- Revocation ---
    # "Unpublish" means "stop offering". Copies a harvester already took live
    # in someone else's system, and owners are told so rather than promised a
    # recall the Bureau does not have (ADR5, 3.6).
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Relationships ---
    thing: Mapped["Thing"] = relationship("Thing", viewonly=True)
    destination: Mapped["Destination"] = relationship("Destination", viewonly=True)
    contact: Mapped[Optional["Contact"]] = relationship("Contact", viewonly=True)

    __table_args__ = (
        # One live row per (thing, destination, data type). Revoked rows stay
        # for the history, so the constraint has to ignore them.
        Index(
            "uq_publication_consent_live",
            "thing_id",
            "destination_id",
            "data_type",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    def __str__(self):
        return f"thing {self.thing_id} -> destination {self.destination_id} ({self.data_type})"


# ============= EOF =============================================
