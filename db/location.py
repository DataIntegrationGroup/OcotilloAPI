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
from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    func,
    Text,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin


class Location(Base, AutoBaseMixin, ReleaseMixin):
    # name = Column(String(100), nullable=True)
    # description = Column(String(255), nullable=True)
    # visible = Column(Boolean, default=False, nullable=False)
    __versioned__ = {}

    name = mapped_column(String(255), nullable=True)
    notes = mapped_column(Text, nullable=True)
    point: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )


class LocationThingAssociation(Base, AutoBaseMixin):
    location_id = Column(
        Integer, ForeignKey("location.id", ondelete="CASCADE"), primary_key=True
    )
    thing_id = Column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), primary_key=True
    )

    # REFACTOR TODO: when refactoring/updating location/thing schemas and tests, ensure timezone is UTC
    effective_start = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.timezone("UTC", func.now()),
    )
    effective_end = Column(DateTime(timezone=True), nullable=True)

    location = relationship("Location")
    thing = relationship("Thing")



# ============= EOF =============================================
