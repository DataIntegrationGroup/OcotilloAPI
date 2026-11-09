"""
db/site_activity_consent.py

This model defines the `SiteActivityConsent` table, a polymorphic table that
records what an owner allows the Bureau to do at their site: measure water
levels, sample water chemistry, install a datalogger. Each record says who
consented, to which activity, whether it is allowed, which entity it applies
to, and for what period of time.

This is the owner's decision, not staff authorization. What staff may do is
`PermissionGrant` (db/permission_grant.py). See ADR5.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Integer, ForeignKey, String, and_
from sqlalchemy.orm import relationship, Mapped, mapped_column, declared_attr, foreign

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.contact import Contact
    from db.thing import Thing
    from db.location import Location


class SiteActivityConsent(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents one owner's consent, or refusal, for one activity at a
    specific entity (e.g., a Thing or Location).
    """

    # --- Foreign Keys ---
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )

    # --- Columns ---
    activity: Mapped[str] = lexicon_term(nullable=False)
    allowed: Mapped[bool] = mapped_column(nullable=False, default=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(nullable=True)

    # --- Polymorphic Columns ---
    target_id: Mapped[int] = mapped_column(nullable=False)
    target_table: Mapped[str] = mapped_column(String(50), nullable=False)

    # --- Relationships ---
    # Many-To-One: A consent is given by one Contact.
    contact: Mapped["Contact"] = relationship(
        "Contact", back_populates="site_activity_consents"
    )

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are view-only relationships used by the 'target' property below.
    # They tell SQLAlchemy exactly how to find the specific parent record for a given child.
    _thing_target: Mapped["Thing"] = relationship(
        "Thing",
        primaryjoin="and_(foreign(SiteActivityConsent.target_id) == Thing.id, "
        "SiteActivityConsent.target_table == 'thing')",
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin="and_(foreign(SiteActivityConsent.target_id) == Location.id, "
        "SiteActivityConsent.target_table == 'location')",
        viewonly=True,
    )

    @property
    def target(self):
        """
        A generic property to get the parent object (Thing, Location, etc.).
        This is useful for simplifying application code by providing a single,
        consistent way to access the parent of a polymorphic record.
        """
        return getattr(self, f"_{self.target_table}_target")


class SiteActivityConsentMixin:
    """
    Mixin for models that can have site activity consents (e.g., Thing,
    Location). It automatically creates a polymorphic One-to-Many relationship
    to the SiteActivityConsent table.
    """

    @declared_attr
    def site_activity_consent(cls):
        # One-to-Many polymorphic relationship. Named after the table, like
        # status_history, because services/util.py looks the type column up
        # by relationship name.
        return relationship(
            "SiteActivityConsent",
            primaryjoin=(
                and_(
                    cls.id == foreign(SiteActivityConsent.target_id),
                    SiteActivityConsent.target_table == cls.__tablename__,
                )
            ),
            lazy="selectin",
            viewonly=True,
        )
