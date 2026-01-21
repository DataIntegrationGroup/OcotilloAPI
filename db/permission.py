"""
models/permission.py

This model defines the `Permission` table, a polymorphic table that tracks
all legal and administrative agreements related to site access and activity.
Its purpose is to track who granted permission, what activities they authorized,
which entity the permission applies to, and for what period of time.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Integer,
    ForeignKey,
    String,
    Boolean,
    Date,
    Text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin

if TYPE_CHECKING:
    from db.contact import Contact
    from db.thing import Thing
    from db.location import Location


class Permission(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a specific grant of permission from a Contact for a
    specific entity (e.g., a Thing or Location).
    """

    # --- Foreign Keys ---
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.id"), nullable=False
    )

    # --- Columns ---
    allow_sampling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_installation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    start_date: Mapped[Date] = mapped_column(Date, nullable=True)
    end_date: Mapped[Date] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # --- Polymorphic Columns ---
    permissible_id: Mapped[int] = mapped_column(Integer, nullable=False)
    permissible_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # --- Relationships ---
    # Many-To-One: A Permission is granted by one Contact.
    contact: Mapped["Contact"] = relationship("Contact", back_populates="permissions")

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are view-only relationships used by the 'target' property below.
    # They tell SQLAlchemy exactly how to find the specific parent record for a given child.
    _thing_target: Mapped["Thing"] = relationship(
        "Thing",
        primaryjoin="and_(foreign(Permission.permissible_id) == Thing.id, "
        "Permission.permissible_type == 'Thing')",
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin="and_(foreign(Permission.permissible_id) == Location.id, "
        "Permission.permissible_type == 'Location')",
        viewonly=True,
    )

    @property
    def target(self):
        """
        A generic property to get the parent object (Thing, Location, etc.).
        This is useful for simplifying application code by providing a single,
        consistent way to access the parent of a polymorphic record.
        """
        return getattr(self, f"_{self.permissible_type.lower()}_target")
