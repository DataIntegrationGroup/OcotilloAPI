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
from sqlalchemy import Integer, ForeignKey, String, Column, Float, Text
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy_utils import TSVectorType

from db import lexicon_term
from db.asset import Asset
from db.base import (
    AutoBaseMixin,
    Base,
    ReleaseMixin,
    StatusHistoryMixin,
    PermissionMixin,
)

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from db.location import Location
    from db.field import FieldEvent
    from db.deployment import Deployment
    from db.sensor import Sensor
    from db.contact import Contact


class Thing(Base, AutoBaseMixin, ReleaseMixin, StatusHistoryMixin, PermissionMixin):
    """
    Represents a physical object of interest being monitored (e.g., a well).
    Stores static, core attributes of the physical installation.
    """

    # --- Foreign Keys ---
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("location.id"), nullable=False
    )

    # --- Columns ---
    # TODO: should `name` be unique?
    name: Mapped[str] = mapped_column(
        nullable=False,
        comment="The name of the thing (e.g., well name or identifier).",
    )
    # TODO: what is the purpose of the `description` field?
    description: Mapped[str] = mapped_column(String(500))
    thing_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field defining the type of infrastructure (e.g., 'Well', 'Spring', 'Stream Gauge').",
    )

    # --- Relationships ---
    asset_associations = relationship(
        "AssetThingAssociation",
        back_populates="thing",
        overlaps="things",
        cascade="all, delete-orphan",
    )

    location_associations = relationship(
        "LocationThingAssociation",
        back_populates="thing",
        overlaps="location",
        cascade="all, delete-orphan",
        order_by="LocationThingAssociation.effective_start.desc()",
    )

    contact_associations = relationship(
        "ThingContactAssociation",
        back_populates="thing",
        overlaps="contacts",
        cascade="all, delete-orphan",
    )

    # --- Association Proxies ---
    assets: AssociationProxy[list["Asset"]] = association_proxy(
        "asset_associations", "asset"
    )

    locations: AssociationProxy[list["Location"]] = association_proxy(  # noqa: F821
        "location_associations", "location"
    )

    # Proxy to directly access the Contact objects associated with this Thing
    contacts: AssociationProxy[list["Contact"]] = association_proxy(  # noqa: F821
        "contact_associations", "contact"
    )

    # Proxy to directly access the Sensor (Equipment) deployed at this Thing.
    sensor: AssociationProxy[List["Sensor"]] = association_proxy(
        "deployments", "sensor"
    )

    # Well-related fields
    well_depth: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        info={"unit": "feet below ground surface"},
        comment="Total depth of the well, from ground surface to the bottom of the well (in feet).",
    )
    hole_depth: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        info={"unit": "feet below ground surface"},
        comment="Depth of the drilled hole, from ground surface to the bottom of the borehole (in feet).",
    )
    well_purpose: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field defining the primary function of the well (e.g., 'Monitoring', 'Irrigation', 'Domestic', 'Livestock', 'Remediation').",
    )
    well_casing_diameter: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        info={"unit": "inches"},
        comment="Diameter of the well casing in inches.",
    )
    well_casing_depth: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        info={"unit": "feet below ground surface"},
        comment="Depth of the well casing from ground surface to the bottom of the casing (in feet).",
    )
    well_casing_material: Mapped[str] = lexicon_term(
        nullable=True,
        comment="Material of the well casing (e.g., 'PVC', 'Steel', 'Concrete', 'Wood').",
    )

    well_construction_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # Spring-related fields
    spring_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field defining the type of spring (e.g., 'Mineral', 'Artesian', 'Seep', etc.).",
    )

    search_vector = Column(
        TSVectorType(
            "name", "well_construction_notes", "well_type", "well_casing_description"
        )
    )

    # --- Relationships ---
    # One-To-Many: A Thing can have many FieldEvents over time.
    field_events: Mapped[List["FieldEvent"]] = relationship(
        "FieldEvent", back_populates="thing", cascade="all, delete-orphan", uselist=True
    )

    # One-To-Many: A Thing can have many Deployments of sensors (equipment) over time.
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="thing", cascade="all, delete-orphan"
    )

    # --- Association Proxies ---
    # Proxy to directly access the Sensor deployed at this Thing.
    sensors: AssociationProxy[List["Sensor"]] = association_proxy(
        "deployments", "sensor"
    )


class ThingIdLink(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a link associated with a Thing.
    """

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = lexicon_term(nullable=False)
    alternate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    alternate_organization: Mapped[str] = lexicon_term(nullable=False)

    thing: Mapped["Thing"] = relationship("Thing", backref="links")


class WellScreen(Base, AutoBaseMixin, ReleaseMixin):
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    screen_depth_top: Mapped[float] = mapped_column(
        info={"unit": "feet below ground surface"}, nullable=True
    )
    screen_depth_bottom: Mapped[float] = mapped_column(
        info={"unit": "feet below ground surface"}, nullable=True
    )
    screen_type: Mapped[str] = lexicon_term(nullable=True)  # e.g., "PVC", "Steel", etc.

    screen_description: Mapped[str] = mapped_column(
        String(1000), info={"unit": "description of the screen"}, nullable=True
    )
    nma_pk_wellscreens: Mapped[str] = mapped_column(String(100), nullable=True)

    # Define a relationship to well if needed
    thing: Mapped["Thing"] = relationship("Thing")


# TODO: this could be the model used to handle AMP monitoring
# class FieldSamplingAdministation(Base, AutoBaseMixin):
#     # the thing being monitored
#     thing_id: Mapped[int] = mapped_column(Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False)
#
#     monitoring_frequency: Mapped[str] = mapped_column(lexicon_term(), nullable=False)
#     well_logger_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
#     monitor_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
#     sample_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)


# ============= EOF =============================================
