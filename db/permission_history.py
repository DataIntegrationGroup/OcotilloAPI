"""
models/permission.py

This model defines the `Permission` table, a polymorphic table that tracks
all legal and administrative agreements related to site access and activity.
Its purpose is to track who granted permission, what activities they authorized,
which entity the permission applies to, and for what period of time.
"""

from typing import TYPE_CHECKING
from datetime import date
from sqlalchemy import Integer, ForeignKey, String, and_
from sqlalchemy.orm import relationship, Mapped, mapped_column, declared_attr, foreign

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term, pascal_to_snake


if TYPE_CHECKING:
    from db.contact import Contact
    from db.thing import Thing
    from db.location import Location


class PermissionHistory(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a specific grant of permission from a Contact for a
    specific entity (e.g., a Thing or Location).
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
        primaryjoin="and_(foreign(PermissionHistory.target_id) == Thing.id, "
        "PermissionHistory.target_table == 'thing')",
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin="and_(foreign(PermissionHistory.target_id) == Location.id, "
        "PermissionHistory.target_table == 'location')",
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


class PermissionHistoryMixin:
    """
    Mixin for models that can have permissions (e.g., Thing, Location).
    It automatically creates a polymorphic One-to-Many relationship to the
    Permission table.
    """

    @declared_attr
    def permission_history(cls):
        # One-to-Many polymorphic relationship
        return relationship(
            "PermissionHistory",
            primaryjoin=(
                and_(
                    cls.id == foreign(PermissionHistory.target_id),
                    PermissionHistory.target_table == pascal_to_snake(cls.__name__),
                )
            ),
            lazy="selectin",
            viewonly=True,
        )
