"""
SQLAlchemy model for the GeologicFormation table.

This table is a master reference table for geologic formations. Its purpose is to store definitions and descriptions
of various geologic formations that can be referenced by other tables in the database.
"""

from typing import List, TYPE_CHECKING

from geoalchemy2 import Geometry
from sqlalchemy import Text, Index
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.constants import SRID_WGS84
from db.base import Base, AutoBaseMixin, ReleaseMixin
from db.lexicon import lexicon_term

if TYPE_CHECKING:
    from db.thing import Thing, WellScreen
    from db.stratigraphic_interval import StratigraphicInterval


class GeologicFormation(Base, AutoBaseMixin, ReleaseMixin):
    __versioned__ = {}

    # TODO: Let the API map formation codes to names using a formations.json file that can be periodically updated
    #  from the authoritative source (.e.g USGS). A placeholder `formations.json` file had been added to the `core`
    #  directory.
    # name: Mapped[str] = mapped_column(
    #     nullable=False,
    #     unique=True,
    #     comment="The full, human-readable name of the geologic formation (e.g., 'Navajo Sandstone').",
    # )
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
    lithology: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary for the primary, dominant rock type"
        "(e.g., 'Tuff', 'Sandstone', 'Alluvium', 'Shale').",
    )
    boundary: Mapped[Geometry] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID_WGS84, spatial_index=True),
        nullable=True,
        comment="A spatial representation of the geologic formation's extent.",
    )

    # --- Relationships ---
    # One-To-Many: the stratigraphic intervals (in any well) that fall in this
    # formation. Deleting a formation keeps the intervals; the database sets
    # their geologic_formation_id to NULL.
    stratigraphic_intervals: Mapped[List["StratigraphicInterval"]] = relationship(
        "StratigraphicInterval",
        back_populates="geologic_formation",
        passive_deletes=True,
    )
    # One-To-Many: A GeologicFormation can have many physical WellScreens installed in it.
    well_screens: Mapped[List["WellScreen"]] = relationship(
        "WellScreen", back_populates="geologic_formation", passive_deletes=True
    )

    # --- Association Proxies ---
    # Provides direct access to Things (wells) that penetrate this formation.
    things: AssociationProxy["Thing"] = association_proxy(
        "stratigraphic_intervals", "thing"
    )

    # --- Table Arguments ---
    __table_args__ = (Index("ix_geologicformation_formation_code", "formation_code"),)
