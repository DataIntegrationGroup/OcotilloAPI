"""
SQLAlchemy model for the ThingAquiferAssociation table.

This table is a join table (or "association object") whose purpose is to manage
the many-to-many relationship between a Thing and an AquiferSystem.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin

if TYPE_CHECKING:
    from db.thing import Thing
    from db.aquifer_system import AquiferSystem


class ThingAquiferAssociation(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents the association of a Thing to an AquiferSystem. This is an Association Object.
    """

    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    aquifer_system_id: Mapped[int] = mapped_column(
        ForeignKey("aquifer_system.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationship Definitions ---
    # Many-To-One: This association links to one Thing.
    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="aquifer_associations", lazy="joined"
    )

    # Many-To-One: This association links to one AquiferSystem.
    aquifer_system: Mapped["AquiferSystem"] = relationship(
        "AquiferSystem", back_populates="thing_associations", lazy="joined"
    )
