"""
This table is a controlled vocabulary for all analytes, properties, and
characteristics that can be measured or observed.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.observation import Observation
    from db.regulatory_limit import RegulatoryLimit


class Parameter(Base, AutoBaseMixin, ReleaseMixin):
    """

    Represents an analyte or property that can be measured (e.g., Chloride).
    """

    __versioned__ = {}

    # --- Columns ---
    # TODO: Parameter names are currently associated with the 'observed_property' category in the lexicon. Should we update the lexicon category name to 'parameter_name'?
    parameter_name: Mapped[str] = lexicon_term(
        nullable=False,
        unique=True,
        comment="The official, full name of the parameter (e.g., 'Arsenic, Dissolved').",
    )
    parameter_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field defining the category of the parameter (e.g., 'Metals', 'Nutrients', 'Field Parameter'). Used for grouping and filtering.",
    )
    cas_number: Mapped[str] = mapped_column(
        nullable=True,
        comment="he Chemical Abstracts Service (CAS) registry number, a globally unique identifier for a chemical substance.",
    )
    default_unit: Mapped[str] = lexicon_term(
        nullable=False,
        comment="The standard, preferred unit for reporting this parameter (e.g., 'ug/L', 'mg/L', 'pH units').",
    )

    # --- Relationships ---
    # One-To-Many: A Parameter can have many Observations.
    observations: Mapped[List["Observation"]] = relationship(
        "Observation", back_populates="parameter"
    )

    # One-To-Many: A Parameter can have many associated RegulatoryLimits.
    # If a Parameter is deleted, all its associated limits are deleted as well.
    reg_limits: Mapped[List["RegulatoryLimit"]] = relationship(
        "RegulatoryLimit", back_populates="parameter", cascade="all, delete-orphan"
    )
