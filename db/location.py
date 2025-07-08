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
    Boolean,
    DateTime,
    func,
)
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin


class Location(Base, AutoBaseMixin):
    name = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    visible = Column(Boolean, default=False, nullable=False)

    point: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    )

    thing = association_proxy("location_thing_association", "thing")
    # owner_id = Column(
    #     Integer, ForeignKey("owner.id", ondelete="CASCADE"), nullable=True
    # )


class LocationThingAssociation(Base, AutoBaseMixin):
    location_id = Column(
        Integer, ForeignKey("location.id", ondelete="CASCADE"), primary_key=True
    )
    thing_id = Column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), primary_key=True
    )

    effective_start = Column(DateTime, nullable=False, server_default=func.now())
    effective_end = Column(DateTime, nullable=True)

    # location = relationship("Location", back_populates="thing")
    # thing = relationship("Thing", back_populates="locations")


# class Owner(Base, AutoBaseMixin):
#     name = Column(String(100), nullable=False, unique=True)
#     description = Column(String(255), nullable=True)
#
#     search_vector = Column(TSVectorType("name", "description"))
#
#     contacts = relationship(
#         "Contact",
#         secondary="owner_contact_association",
#     )
#     # contacts = relationship(
#     #     "Contact", back_populates="owner", cascade="all, delete-orphan"
#     # )


# class Equipment(Base, AutoBaseMixin):
#     equipment_type = Column(String(50))
#     model = Column(String(50))
#     serial_no = Column(String(50))
#     date_installed = Column(DateTime)
#     date_removed = Column(DateTime)
#     recording_interval = Column(Integer)
#     equipment_notes = Column(String(50))
#     location_id = Column(
#         Integer, ForeignKey("location.id", ondelete="CASCADE"), nullable=False
#     )
#
#     location = relationship("Location")

# class Spring(Base):
#     __tablename__ = 'Spring'
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     location_id = Column(Integer, ForeignKey('samplelocation.id'), nullable=False)
#
#     # Define a relationship to samplelocation if needed
#     location = relationship("samplelocation")
#
#
# class Stream(Base):
#     __tablename__ = 'Stream'
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     location_id = Column(Integer, ForeignKey('samplelocation.id'), nullable=False)
#
#     # Define a relationship to samplelocation if needed
#     location = relationship("samplelocation")
#
#
# class Surface(Base):
#     __tablename__ = 'Surface'
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     location_id = Column(Integer, ForeignKey('samplelocation.id'), nullable=False)
#
#     # Define a relationship to samplelocation if needed
#     location = relationship("samplelocation")
#
#
# class Subsurface(Base):
#     __tablename__ = 'Subsurface'
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     location_id = Column(Integer, ForeignKey('samplelocation.id'), nullable=False)
#
#     # Define a relationship to samplelocation if needed
#     location = relationship("samplelocation")
#


# ============= EOF =============================================
