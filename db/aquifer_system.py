"""
SQLAlchemy model for the AquiferSystem table.

This is a master reference table for aquifer systems and hydrogeologic units.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy import Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from geoalchemy2 import Geometry

from db.base import Base, AutoBaseMixin, ReleaseMixin
from db.lexicon import lexicon_term

from constants import SRID_WGS84

if TYPE_CHECKING:
    from db.thing import WellScreen, ThingAquiferAssociation, Thing
    from db.aquifer_type import AquiferType


class AquiferSystem(Base, AutoBaseMixin, ReleaseMixin):
    __versioned__ = {}

    name: Mapped[str] = mapped_column(
        nullable=False,
        unique=True,
        comment="The full, human-readable name of the aquifer system (e.g., 'Ogallala Aquifer').",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="A detailed description of the aquifer system, its characteristics, and its significance.",
    )
    # Lexicon terms were retrieved from NMAquifer's 'LU_AquiferType' table.
    primary_aquifer_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field to classify the aquifer's primary hydrologic properties (e.g., 'Unconfined', 'Confined', 'Perched').",
    )
    geographic_scale: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field to classify the aquifer's geographic scale (e.g., 'Major', 'Regional', 'Local').",
    )
    boundary: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID_WGS84, spatial_index=True),
        nullable=True,
        comment="A spatial representation of the aquifer system's boundary.",
    )
    # Hierarchical relationship fields (may be implemented in future iterations)
    # Example: High Plains Aquifer (parent) contains Ogallala Aquifer (child)
    # parent_id = Column(Integer, ForeignKey('aquifer_system.id'))
    # parent = relationship('AquiferSystem', remote_side=[id], backref='subsystems')

    # --- Relationships ---
    # One-To-Many: An AquiferSystem can be associated with many wells (Things) via the ThingAquiferAssociation join table.
    thing_associations: Mapped[List["ThingAquiferAssociation"]] = relationship(
        "ThingAquiferAssociation",
        back_populates="aquifer_system",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # One-To-Many: An AquiferSystem can be the target for many individual WellScreens.
    well_screens: Mapped[List["WellScreen"]] = relationship(
        "WellScreen",
        back_populates="aquifer_system",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Association Proxies ---
    # Proxy to directly access Things (wells) associated with this AquiferSystem.
    things: AssociationProxy[List["Thing"]] = association_proxy(
        "thing_associations", "thing"
    )
    # Proxy to directly access all AquiferTypes associated with this AquiferSystem.
    aquifer_types: AssociationProxy[List["AquiferType"]] = association_proxy(
        "thing_associations", "aquifer_types"
    )

    # --- Table Arguments ---
    __table_args__ = Index("ix_aquifersystem_name", "name")
