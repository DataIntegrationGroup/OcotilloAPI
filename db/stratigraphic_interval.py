"""
SQLAlchemy model for the StratigraphicInterval table.

One row is one depth interval in a well's stratigraphic log: where it starts
and ends, which geologic formation it falls in (if known), and what rock it is.
It mirrors a legacy NM_Aquifer ``Stratigraphy`` row.

The table was ``thing_geologic_formation_association`` until BDMS-1554. It was
renamed because an interval is not just a formation pick: legacy intervals can
carry a lithology without a formation, and lithology varies within a formation.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term
from db.notes import NotesMixin

if TYPE_CHECKING:
    from db.thing import Thing
    from db.geologic_formation import GeologicFormation


class StratigraphicInterval(Base, AutoBaseMixin, ReleaseMixin, NotesMixin):
    """A depth interval in a well's stratigraphic log."""

    # --- Foreign Keys ---
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"),
        nullable=False,
        comment="The well this interval belongs to. Deleting the well deletes "
        "its stratigraphic log.",
    )
    geologic_formation_id: Mapped[int | None] = mapped_column(
        ForeignKey("geologic_formation.id", ondelete="SET NULL"),
        nullable=True,
        comment="The geologic formation this interval falls in, if known. "
        "Deleting a formation keeps the interval and clears this link.",
    )

    # --- Depth interval ---
    top_depth: Mapped[float] = mapped_column(
        nullable=False,
        comment="Depth (in feet below ground surface) to the top of the interval.",
    )
    bottom_depth: Mapped[float] = mapped_column(
        nullable=False,
        comment="Depth (in feet below ground surface) to the bottom of the interval.",
    )

    # --- Description ---
    lithology: Mapped[str | None] = lexicon_term(
        nullable=True,
        comment="The rock type of this interval, from the lithology lexicon "
        "(legacy Stratigraphy.Lithology via LU_Lithology).",
    )
    lithologic_modifier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text qualifier on the lithology, e.g. color or grain size "
        "(legacy Stratigraphy.LithologicModifier).",
    )
    contributing_unit: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether this interval contributes water to the well "
        "(legacy Stratigraphy.ContributingUnit).",
    )
    source: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Where the interval was described, e.g. a driller's log "
        "(legacy Stratigraphy.StratSource). Published as NGWMN StratSource.",
    )

    # --- Legacy ---
    nma_pk_stratigraphy: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        unique=True,
        comment="Legacy NM_Aquifer Stratigraphy.GlobalID this interval was "
        "migrated from.",
    )

    # --- Relationship Definitions ---
    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="stratigraphic_intervals"
    )
    geologic_formation: Mapped["GeologicFormation"] = relationship(
        "GeologicFormation", back_populates="stratigraphic_intervals"
    )
