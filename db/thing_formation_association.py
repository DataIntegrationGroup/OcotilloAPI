"""
SQLAlchemy model for the ThingFormationAssociation table.

This table is an association object that creates a many-to-many relationship between a Thing (well) and a
GeologicFormation. It stores the lithology for a well, detailing the depth intervals for each formation it penetrates.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin

if TYPE_CHECKING:
    from db.thing import Thing
    from db.geologic_formation import GeologicFormation


class ThingFormationAssociation(Base, AutoBaseMixin, ReleaseMixin):
    """
    This is a= join table (Association Object). It represents the association of a Thing to a
    GeologicFormation at a specific depth interval.
    """

    # --- Foreign Keys ---
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"),
        nullable=False,
        comment="The foreign key linking this record to the `Thing` table."
        "Deleting a `Thing` will cascade and delete its formation log.",
    )
    geologic_formation_id: Mapped[int] = mapped_column(
        ForeignKey("geologic_formation.id", ondelete="SET NULL"),
        nullable=True,
        comment="The foreign key linking this record to the `GeologicFormation` table."
        "This is set to `SET NULL` on delete, as deleting a formation definition (a rare admin action)"
        "should not delete the historical fact that a well had a pick at this depth.",
    )

    # Depth interval fields
    top_depth: Mapped[float] = mapped_column(
        nullable=False,
        comment="The depth (in feet) to the top of the geologic formation, as measured from ground surface.",
    )
    bottom_depth: Mapped[float] = mapped_column(
        nullable=False,
        comment="The depth (in feet) to the bottom of the geologic formation, as measured from ground surface.",
    )

    # --- Relationship Definitions ---
    # Many-To-One: This association links to one Thing.
    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="formation_associations", lazy="joined"
    )

    # Many-To-One: This association links to one GeologicFormation.
    geologic_formation: Mapped["GeologicFormation"] = relationship(
        "GeologicFormation", back_populates="thing_associations", lazy="joined"
    )
