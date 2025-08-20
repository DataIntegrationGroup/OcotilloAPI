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
from typing import Optional

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.testing.schema import mapped_column

from db.base import Base, AutoBaseMixin


class Group(Base, AutoBaseMixin):
    # --- Column Definitions ---
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    project_area: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True)
    )

    # Foreign Keys
    parent_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=True
    )

    # --- Relationship Definitions ---
    things = relationship("Thing", secondary="group_thing_association")


class GroupThingAssociation(Base, AutoBaseMixin):
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False
    )
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )


# ============= EOF =============================================
