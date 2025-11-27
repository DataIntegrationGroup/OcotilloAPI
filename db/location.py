# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from geoalchemy2 import Geometry, WKBElement, WKTElement
from geoalchemy2.shape import to_shape
from sqlalchemy import (
    String,
    ForeignKey,
    DateTime,
    Date,
    func,
    Text,
)
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.orm import relationship, Mapped, mapped_column

from constants import SRID_WGS84
from db.base import Base, AutoBaseMixin, ReleaseMixin
from db.data_provenance import DataProvenanceMixin
from db.notes import NotesMixin

if TYPE_CHECKING:
    from db.thing import Thing


class Location(Base, AutoBaseMixin, ReleaseMixin, NotesMixin, DataProvenanceMixin):
    __versioned__ = {}

    nma_pk_location: Mapped[UUID] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column
    # name: Mapped[str] = mapped_column(String(255), nullable=True)
    point: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID_WGS84, spatial_index=True)
    )
    elevation: Mapped[float] = mapped_column(
        nullable=False, comment="in meters with vertical datum of NAVD88"
    )

    # state: Mapped[str] = lexicon_term(nullable=True, default="New Mexico")
    # county: Mapped[str] = lexicon_term(nullable=True)
    county: Mapped[str] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(100), nullable=True)
    quad_name: Mapped[str] = mapped_column(String(100), nullable=True)
    # TODO: remove this 'notes' field in favor of using the polymorphic Notes table. Did not remove it yet to avoid breaking existing data model.
    # notes: Mapped[str] = mapped_column(Text, nullable=True)
    nma_notes_location: Mapped[str] = mapped_column(Text, nullable=True)
    nma_coordinate_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # --- Legacy AMPAPI Date Fields (Migration-Only, Read-Only Post-Migration) ---
    legacy_date_created: Mapped[datetime.date] = mapped_column(
        Date, nullable=True, comment="Original AMPAPI DateCreated (migration-only field)"
    )
    legacy_site_date: Mapped[datetime.date] = mapped_column(
        Date, nullable=True, comment="Original AMPAPI SiteDate (migration-only field)"
    )

    # --- Relationship Definitions ---
    thing_associations: Mapped[list["LocationThingAssociation"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    # --- Proxy Definitions ---
    things: AssociationProxy[list["Thing"]] = association_proxy(
        "thing_associations", "thing"
    )

    @property
    def latlon(self):
        point = self.point

        if isinstance(point, str):
            point = WKTElement(point)

        p = to_shape(point)
        return p.y, p.x

    @property
    def elevation_method(self) -> str | None:
        return self._get_data_provenance_attribute("elevation", "collection_method")


class LocationThingAssociation(Base, AutoBaseMixin):
    location_id: Mapped[int] = mapped_column(
        ForeignKey("location.id", ondelete="CASCADE"), primary_key=True
    )
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"), primary_key=True
    )

    # REFACTOR TODO: when refactoring/updating location/thing schemas and tests, ensure timezone is UTC
    effective_start: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
    )
    effective_end: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationship Definitions ---
    location: Mapped["Location"] = relationship(
        back_populates="thing_associations", lazy="joined"
    )
    thing: Mapped["Thing"] = relationship(back_populates="location_associations")


# ============= EOF =============================================
