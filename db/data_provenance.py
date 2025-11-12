"""
SQLAlchemy model for the Provenance table.

This is the central polymorphic repository for all provenance (origin) metadata
for foundational or static data in the database, such as elevation details or
well construction information.

***NOTE:***
This table is **not** used to store routine, transactional analytical metadata
(such as lab qualifiers, detection limits, or analysis dates). That information
is an intrinsic part of a lab result and is stored in the `Observation` and
`LabLimit` tables. This table is for sourcing foundational data, such as a well's
construction details or a site's coordinates.

"""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin

from db import lexicon_term

if TYPE_CHECKING:
    from db.thing import Thing
    from db.location import Location


class DataProvenance(AutoBaseMixin, ReleaseMixin, Base):
    """
    Represents  a single piece of provenance metadata that can be attached to
    any other record or field in the database.
    """

    # --- Polymorphic Columns ---
    target_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="The primary key (`id`) of the parent record this metadata is about (e.g., the `thing_id` of a well).",
    )
    target_table: Mapped[str] = mapped_column(
        nullable=False,
        comment="The name of the parent table this metadata is for (e.g., 'Thing', 'Location', etc).",
    )

    # --- Columns ---
    field_name: Mapped[str] = mapped_column(
        nullable=True,
        comment="The specific column in the parent table that this metadata applies to (e.g., 'well_depth_ft', 'coordinates')."
        "If `NULL`, the record applies to the entire parent object.",
    )
    # TODO: Values from the following NMAquifer tables should be included as terms in the lexicon:
    #  'LU_DataSource', 'LU_Depth_CompletionSource'.
    origin_source: Mapped[str] = lexicon_term(
        nullable=True,
        comment="Indicates the origin source of the data (e.g'Driller's Log', 'Well Report'.",
    )
    # TODO: Values from the following NMAquifer tables should be included as terms in the lexicon:
    #  'LU_AltitudeMethod','LU_CoordinateMethod'.
    collection_method: Mapped[str] = lexicon_term(
        nullable=True,
        comment="Indicates the method used to collect the data (e.g., 'GPS - Survey Grade').",
    )
    # TODO: Values from the following NMAquifer tables should be included as terms in the lexicon: 'LU_CoordinateAccuracy'.
    accuracy_value: Mapped[float] = mapped_column(
        nullable=True, comment="A numeric value representing the data's accuracy."
    )
    # TODO: Values from the following NMAquifer tables should be included as terms in the lexicon: 'LU_CoordinateAccuracy'.
    accuracy_unit: Mapped[str] = lexicon_term(
        nullable=True,
        comment="The unit for the `accuracy_value` (e.g., 'meters', 'feet').",
    )

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are view-only relationships used by the 'target' property below.
    # They tell SQLAlchemy exactly how to find the specific parent record for a given child.
    _thing_target: Mapped["Thing"] = relationship(
        "Thing",
        primaryjoin="and_(foreign(DataProvenance.target_id) == Thing.id, DataProvenance.target_table == 'Thing')",
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin="and_(foreign(DataProvenance.target_id) == Location.id, DataProvenance.target_table == 'Location')",
        viewonly=True,
    )

    @property
    def target(self):
        """
        A generic property to get the parent object (Thing, Location, etc.).
        This is useful for simplifying application code by providing a single,
        consistent way to access the parent of a polymorphic record.
        """
        return getattr(self, f"_{self.target_table.lower()}_target")

    # --- Table Arguments ---
    __table_args__ = (
        # Composite index for fast polymorphic lookups
        Index("ix_provenance_targets", "target_id", "target_table"),
    )
