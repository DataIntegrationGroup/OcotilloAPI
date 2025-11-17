"""
SQLAlchemy model for the GeologicFormation table.

This table is a master reference table for geologic formations. Its purpose is to store definitions and descriptions
of various geologic formations that can be referenced by other tables in the database.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy import Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from geoalchemy2 import Geometry

from db.base import Base, AutoBaseMixin, ReleaseMixin
from db.lexicon import lexicon_term

if TYPE_CHECKING:
    from db.thing import Thing
    from db.thing_formation_association import ThingFormationAssociation


class GeologicFormation(Base, AutoBaseMixin, ReleaseMixin):
    __versioned__ = {}

    # TODO: Should `name` use a controlled vocabulary?
    name: Mapped[str] = mapped_column(
        nullable=False,
        unique=True,
        comment="The full, human-readable name of the geologic formation (e.g., 'Navajo Sandstone').",
    )
    formation_code: Mapped[str] = lexicon_term(
        nullable=True,
        unique=True,
        comment="A short code or abbreviation for the geologic formation (e.g., '120ELRT').",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="A detailed description of the geologic formation, its characteristics, and its significance.",
    )
    # TODO: Implement controlled vocabularies for `lithology` using NMAquifer's 'LU_Lithology' table.
    #  This should be implemented after AMMP reviews and cleans up their formation terms and codes.
    lithology: Mapped[str] = mapped_column(
        nullable=True,
        comment="A controlled vocabulary for the primary, dominant rock type"
        "(e.g., 'Tuff', 'Sandstone', 'Alluvium', 'Shale').",
    )
    boundary: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=True,
        comment="A spatial representation of the geologic formation's extent.",
    )

    # --- Relationships ---
    # One-To-Many (Association Object): A GeologicFormation can be associated with many Things (e.g., wells) via the
    # ThingFormationAssociation join table.
    thing_associations: Mapped[List["ThingFormationAssociation"]] = relationship(
        "ThingFormationAssociation",
        back_populates="geologic_formation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # --- Association Proxies ---
    # Provides direct access to Things (wells) that penetrate this formation.
    things: AssociationProxy["Thing"] = association_proxy("thing_associations", "thing")

    # --- Table Arguments ---
    __table_args__ = (
        Index("ix_geologicformation_name", "name"),
        Index("ix_geologicformation_code", "code"),
    )
