"""
This table stores the various regulatory or health-based limits for a given
parameter, sourced from different agencies or standards.

The purpose of this table  is to solve the real-world problem where a single
chemical (`Parameter`) can have multiple different limits set by various agencies
(e.g., a federal EPA limit and a state-level NMED limit).
"""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.parameter import Parameter


class RegulatoryLimit(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, citable regulatory or health-based limit for a
    specific Parameter.
    """

    __versioned__ = {}

    # --- Foreign Keys ---
    parameter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parameter.id"), nullable=False
    )

    # --- Columns ---
    limit_source: Mapped[str] = lexicon_term(
        nullable=False,
        comment="The official source of the limit (e.g., 'EPA', 'NMED', 'EPA').",
    )
    limit_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    limit_unit: Mapped[str] = lexicon_term(nullable=False)
    limit_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field to categorize the limit (e.g., 'MCL', 'PQL', 'MDL', etc.).",
    )

    # --- Relationships ---
    # Many-To-One: A RegulatoryLimit is for one Parameter.
    parameter: Mapped["Parameter"] = relationship(
        "Parameter", back_populates="reg_limits"
    )
