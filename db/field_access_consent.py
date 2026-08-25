"""
db/field_access_consent.py

Landowner consent to physical site access, recorded per Thing or Location.

This is a domain fact, not authorization. A row says a contact agreed to let
the Bureau do something at their well -- sample it, install equipment -- for
some period of time. Nothing here decides what an API caller may see or write;
that is the grant model described in ADR5, which is a separate table with
separate governance.

The table was named `permission_history` until ADR5. The `permission_type`
and `permission_allowed` column names are kept because `permission_type` is
lexicon-backed and both are published in Thing responses as-is.
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


class FieldAccessConsent(Base, AutoBaseMixin, ReleaseMixin):
    """
    One consent record: a Contact agreed (or declined) to a type of field
    activity at a specific entity (a Thing or a Location), over a date range.

    Not an access-control grant. See ADR5.
    """

    # --- Foreign Keys ---
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )

    # --- Columns ---
    permission_type: Mapped[str] = lexicon_term(nullable=False)
    permission_allowed: Mapped[bool] = mapped_column(nullable=False, default=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(nullable=True)

    # --- Polymorphic Columns ---
    target_id: Mapped[int] = mapped_column(nullable=False)
    target_table: Mapped[str] = mapped_column(String(50), nullable=False)

    # --- Relationships ---
    # Many-To-One: A Permission is granted by one Contact.
    contact: Mapped["Contact"] = relationship("Contact", back_populates="permissions")

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are view-only relationships used by the 'target' property below.
    # They tell SQLAlchemy exactly how to find the specific parent record for a given child.
    _thing_target: Mapped["Thing"] = relationship(
        "Thing",
        primaryjoin="and_(foreign(FieldAccessConsent.target_id) == Thing.id, "
        "FieldAccessConsent.target_table == 'thing')",
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin="and_(foreign(FieldAccessConsent.target_id) == Location.id, "
        "FieldAccessConsent.target_table == 'location')",
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


class FieldAccessConsentMixin:
    """
    Mixin for models a landowner can consent about (e.g., Thing, Location).
    It automatically creates a polymorphic One-to-Many relationship to the
    field_access_consent table.
    """

    @declared_attr
    def field_access_consent(cls):
        # One-to-Many polymorphic relationship
        return relationship(
            "FieldAccessConsent",
            primaryjoin=(
                and_(
                    cls.id == foreign(FieldAccessConsent.target_id),
                    FieldAccessConsent.target_table == cls.__tablename__,
                )
            ),
            lazy="selectin",
            viewonly=True,
        )
