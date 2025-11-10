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
from typing import Optional, List, TYPE_CHECKING

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.testing.schema import mapped_column
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy

from constants import SRID_WGS84
from db.base import Base, AutoBaseMixin, ReleaseMixin
from tests.conftest import lexicon_term

if TYPE_CHECKING:
    from db.group import GroupThingAssociation
    from db.thing import Thing


class Group(Base, AutoBaseMixin, ReleaseMixin):
    # --- Column Definitions ---
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    project_area: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID_WGS84, spatial_index=True)
    )
    group_type: Mapped[Optional[str]] = lexicon_term(String(50), nullable=True)
    monitoring_frequency: Mapped[Optional[str]] = lexicon_term(
        String(50), nullable=True
    )

    # Foreign Keys
    parent_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=True
    )

    # --- Relationships ---
    # One-To-Many (Association Object): A Group has many members (Things).
    # The GroupThingAssociation table manages this many-to-many relationship.
    thing_associations: Mapped[List["GroupThingAssociation"]] = relationship(
        "GroupThingAssociation", back_populates="group", cascade="all, delete-orphan"
    )

    # --- Association Proxies ---
    # Many-To-Many Proxy: Provides direct access to the Thing objects in this group.
    things: AssociationProxy[List["Thing"]] = association_proxy(
        "thing_associations", "thing"
    )


class GroupThingAssociation(Base, AutoBaseMixin):
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("group.id", ondelete="CASCADE"), nullable=False
    )
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # --- Relationship Definitions ---
    # Many-To-One: This association links to one Thing.
    thing: Mapped["Thing"] = relationship("Thing", back_populates="group_associations")

    # Many-To-One: This association links to one Group.
    group: Mapped["Group"] = relationship("Group", back_populates="thing_associations")


# ============= EOF =============================================
