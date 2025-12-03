"""
SQLAlchemy model for the AquiferType table.

This table stores the specific aquifer characteristics/types associated with
a Thing-AquiferSystem relationship. It allows capturing that a single aquifer
can have multiple characteristics simultaneously.

Example:
    A well in the "Ogallala" aquifer might tap portions that are both
    "Fractured" AND "Confined". This would create:
    - One AquiferSystem: "Ogallala"
    - One ThingAquiferAssociation: linking well to Ogallala
    - Two AquiferType records: "Fractured" and "Confined"
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.thing_aquifer_association import ThingAquiferAssociation


class AquiferType(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents the specific aquifer types/characteristics for a
    Thing-AquiferSystem association.

    This allows modeling the fact that:
    - A single aquifer can have multiple characteristics
    - Different wells may tap different characteristics of the same aquifer
    - Characteristics are attributes of the relationship, not the aquifer itself

    Fields from WellData CSV:
        - AquiferType: May contain multiple codes (e.g., "FC" = Fractured + Confined)
        - Each code becomes a separate AquiferType record
    """

    # --- Columns ---
    thing_aquifer_association_id: Mapped[int] = mapped_column(
        ForeignKey("thing_aquifer_association.id", ondelete="CASCADE"),
        nullable=False,
        comment="Links to the Thing-Aquifer association this type describes.",
    )
    aquifer_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="Controlled vocabulary for aquifer hydrologic properties. "
        "Examples: 'Unconfined', 'Confined', 'Perched', 'Fractured', 'Unconsolidated'.",
    )

    # --- Relationships ---
    # Many-to-One: Multiple aquifer types can belong to one association
    thing_aquifer_association: Mapped["ThingAquiferAssociation"] = relationship(
        "ThingAquiferAssociation", back_populates="aquifer_types"
    )
