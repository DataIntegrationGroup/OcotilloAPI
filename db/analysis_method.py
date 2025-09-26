"""
This table is a citable library of abstract analytical methods and
standardized field procedures.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.observation import Observation


class AnalysisMethod(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, citable analytical method or standard procedure.
    This is a lookup table.
    """

    # --- Columns ---
    analysis_method_code: Mapped[str] = mapped_column(
        nullable=True,
        unique=True,
        comment="The official code or identifier for the method (e.g., 'EPA 300.0').",
    )
    # TODO: get AMP feedback on if this should be restricted (i.e. lexicon term)
    analysis_method_name: Mapped[str] = mapped_column(
        nullable=False,
        comment="The common, human-readable name of the method (e.g., Ion Chromatography for Anions).",
    )
    analysis_method_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field to categorize the method (e.g., 'Laboratory', 'Field Procedure', 'Calculation').",
    )
    source_organization: Mapped[str] = lexicon_term(
        nullable=True,
        comment="The organization that published the method (e.g., 'US EPA', 'USGS').",
    )

    # --- Relationships ---
    # One-To-Many: An AnalysisMethod can be used for many Observations.
    observations: Mapped[List["Observation"]] = relationship(
        "Observation", back_populates="analysis_method"
    )
