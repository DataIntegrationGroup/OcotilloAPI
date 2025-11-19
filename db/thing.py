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
from typing import List, TYPE_CHECKING
from datetime import date
from sqlalchemy import Integer, ForeignKey, String, Column, Float, Text, Date
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy_utils import TSVectorType

from db import lexicon_term, NotesMixin
from db.asset import Asset
from db.base import (
    AutoBaseMixin,
    Base,
    ReleaseMixin,
)
from db.permission_history import PermissionHistoryMixin
from services.util import retrieve_latest_polymorphic_history_table_record
from db.status_history import StatusHistoryMixin
from db.measuring_point_history import MeasuringPointHistory
from db.data_provenance import DataProvenanceMixin
from services.util import retrieve_latest_polymorphic_history_table_record

if TYPE_CHECKING:
    from db.location import Location
    from db.field import FieldEvent
    from db.deployment import Deployment
    from db.sensor import Sensor
    from db.contact import Contact
    from db.group import Group, GroupThingAssociation


class Thing(
    Base,
    AutoBaseMixin,
    ReleaseMixin,
    StatusHistoryMixin,
    PermissionHistoryMixin,
    DataProvenanceMixin,
    NotesMixin,
):
    """
    Represents a physical object of interest being monitored (e.g., a well).
    Stores static, core attributes of the physical installation.
    """

    __versioned__ = {}

    # --- Columns ---
    nma_pk_welldata: Mapped[str] = mapped_column(
        nullable=True,
        comment="To audit where the data came from in NM_Aquifer if it was transferred over",
    )

    # TODO: should `name` be unique?
    name: Mapped[str] = mapped_column(
        nullable=False,
        comment="The name of the thing (e.g., well name or identifier).",
    )
    # TODO: what is the purpose of the `description` field? Is it ever used?
    # description: Mapped[str] = mapped_column(String(500), nullable=True)
    thing_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field defining the type of infrastructure (e.g., 'Well', 'Spring', 'Stream Gauge').",
    )
    first_visit_date: Mapped[Date] = mapped_column(
        Date,
        nullable=True,
        comment="The date of NMBGMR's first recorded interaction with this specific `Thing`.",
    )
    # Well-related columns
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

    well_construction_notes: Mapped[str] = mapped_column(Text, nullable=True)

    well_completion_date: Mapped[str] = mapped_column(
        Date, nullable=True, comment="the date the well was completed if known"
    )
    well_driller_name: Mapped[str] = mapped_column(
        String(200), nullable=True, comment="Name of the well driller."
    )
    well_construction_method = lexicon_term(nullable=True)
    well_pump_type: Mapped[str] = lexicon_term(nullable=True)
    well_pump_depth: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        info={"unit": "feet below ground surface"},
        comment="Depth of the well pump from ground surface to the pump intake (in feet).",
    )
    # TODO: should this be required for every well in the database? AMMP review
    is_suitable_for_datalogger: Mapped[bool] = mapped_column(
        nullable=True,
        comment="Indicates if the well is suitable for datalogger installation.",
    )

    # Spring-related columns
    spring_type: Mapped[str] = lexicon_term(
        nullable=True,
        comment="A controlled vocabulary field defining the type of spring (e.g., 'Mineral', 'Artesian', 'Seep', etc.).",
    )

    # --- Relationships ---
    # One-To-Many: A Thing can have many associated Assets.
    # If the Thing is deleted, its asset associations will be deleted.
    asset_associations = relationship(
        "AssetThingAssociation",
        back_populates="thing",
        overlaps="things",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # One-To-Many: A Thing can be at many locations over time.
    # If the Thing is deleted, its location history will be deleted.
    """
    Developer's notes

    If there are many location associations related to a thing, eagerly loading
    the location associations may overburden the API and DB and introduce
    performance issues. If this becomes an issue, active/current locations can 
    be fetched in queries when retrieving things. Be thorough if following this
    route as it will need to be included everywhere where a thing record is
    needed, such as for GET /thing, GET /thing/{thing_id}, and GET /contact. See
    below for an example of a way to retrieve the active/current location in a
    query:

    from sqlalchemy.orm import aliased
    from sqlalchemy import select, func

    LTA = aliased(LocationThingAssociation)
    latest_assoc = (
        select(
            LTA.thing_id,
            func.max(LTA.effective_start).label("max_start")
        )
        .where(LTA.effective_end == None)
        .group_by(LTA.thing_id)
        .subquery()
    )

    lta_alias = aliased(LocationThingAssociation)
    query = (
        select(Thing, Location)
        .join(lta_alias, Thing.id == lta_alias.thing_id)
        .join(Location, lta_alias.location_id == Location.id)
        .join(
            latest_assoc,
            (latest_assoc.c.thing_id == lta_alias.thing_id) &
            (latest_assoc.c.max_start == lta_alias.effective_start)
        )
    )
    """
    location_associations = relationship(
        "LocationThingAssociation",
        back_populates="thing",
        overlaps="location",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LocationThingAssociation.effective_start.desc()",
        lazy="joined",
    )

    contact_associations = relationship(
        "ThingContactAssociation",
        back_populates="thing",
        overlaps="contacts",
        cascade="all, delete-orphan",
    )

    # One-To-Many: A Thing can have many FieldEvents over time.
    field_events: Mapped[List["FieldEvent"]] = relationship(
        "FieldEvent",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # One-To-Many: A Thing can have many Deployments of sensors (equipment) over time.
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # One To-Many: A Thing can be in many Groups over time.
    group_associations: Mapped[List["GroupThingAssociation"]] = relationship(
        "GroupThingAssociation",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # One-To-Many: A Thing (well) can have multiple screened intervals.
    screens: Mapped[List["WellScreen"]] = relationship(
        "WellScreen",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    well_purposes: Mapped[List["WellPurpose"]] = relationship(
        "WellPurpose",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )

    well_casing_materials: Mapped[List["WellCasingMaterial"]] = relationship(
        "WellCasingMaterial",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )

    links: Mapped[List["ThingIdLink"]] = relationship(
        "ThingIdLink",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )

    # One-To-Many: A Thing (well) can have multiple measuring points over time.
    measuring_points: Mapped[List["MeasuringPointHistory"]] = relationship(
        "MeasuringPointHistory",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )

    monitoring_frequencies: Mapped[List["MonitoringFrequencyHistory"]] = relationship(
        "MonitoringFrequencyHistory",
        back_populates="thing",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="joined",
    )

    # --- Association Proxies ---
    assets: AssociationProxy[list["Asset"]] = association_proxy(
        "asset_associations", "asset"
    )

    # Proxy to directly access the Location associated with this Thing
    locations: AssociationProxy[list["Location"]] = association_proxy(
        "location_associations", "location"
    )

    # Proxy to directly access the Contact objects associated with this Thing
    contacts: AssociationProxy[list["Contact"]] = association_proxy(
        "contact_associations", "contact"
    )

    # Proxy to directly access the Sensor (Equipment) deployed at this Thing.
    sensor: AssociationProxy[List["Sensor"]] = association_proxy(
        "deployments", "sensor"
    )

    # Proxy to directly access the Group(s) this Thing is a member of.
    groups: AssociationProxy[List["Group"]] = association_proxy(
        "group_associations", "group"
    )

    # Full-text search vector
    search_vector = Column(TSVectorType("name", "well_construction_notes"))

    @property
    def current_location(self):
        """
        Returns the currently active Location by sorting the effective_start
        field. Thing eagerly loads location_association, which eagerly loads
        location, which will hopefully prevent N+1 query problems.
        """
        current_location = sorted(
            self.location_associations, key=lambda x: x.effective_start, reverse=True
        )
        return (
            current_location[0].location
            if current_location and current_location[0].effective_end is None
            else None
        )

    @property
    def water_notes(self):
        return self._get_notes("Water")

    @property
    def general_notes(self):
        return self._get_notes("Other")

    @property
    def measuring_notes(self):
        return self._get_notes("Measuring")

    @property
    def well_status(self) -> str | None:
        """
        Returns the well status from the most recent status history entry
        where status_type is "Well Status".

        Since status_history is eagerly loaded, this should not introduce N+1 query issues.
        """
        latest_status = retrieve_latest_polymorphic_history_table_record(
            self, "status_history", "Well Status"
        )
        return latest_status.status_value if latest_status else None

    @property
    def monitoring_status(self) -> str | None:
        """
        Returns the monitoring status from the most recent status history entry
        where status_type is "Monitoring Status".

        Since status_history is eagerly loaded, this should not introduce N+1 query issues.
        """
        latest_status = retrieve_latest_polymorphic_history_table_record(
            self, "status_history", "Monitoring Status"
        )
        return latest_status.status_value if latest_status else None

    @property
    def measuring_point_height(self) -> int | None:
        """
        Returns the most recent measuring point height from the measuring point history
        table. This assumes that every well has a measuring point

        Since measuring_point_history is eagerly loaded, this should not introduce N+1 query issues.
        """
        if self.thing_type == "water well":
            sorted_measuring_point_history = sorted(
                self.measuring_points, key=lambda x: x.start_date, reverse=True
            )
            return sorted_measuring_point_history[0].measuring_point_height
        else:
            return None

    @property
    def measuring_point_description(self) -> str | None:
        """
        Returns the most recent measuring point description from the measuring point history
        table. This assumes that every well has a measuring point.

        Since measuring_point_history is eagerly loaded, this should not introduce N+1 query issues.
        """
        if self.thing_type == "water well":
            sorted_measuring_point_history = sorted(
                self.measuring_points, key=lambda x: x.start_date, reverse=True
            )
            return sorted_measuring_point_history[0].measuring_point_description
        else:
            return None

    @property
    def well_depth_source(self) -> str | None:
        return self._get_data_provenance_attribute("well_depth", "origin_source")

    @property
    def allow_water_level_samples(self):
        """
        Returns the current permissions for the Thing.
        """
        permission_record = retrieve_latest_polymorphic_history_table_record(
            self, "permission_history", "Water Level Sample"
        )
        return permission_record.permission_allowed if permission_record else None

    @property
    def allow_water_chemistry_samples(self):
        """
        Returns the current permissions for the Thing.
        """
        permission_record = retrieve_latest_polymorphic_history_table_record(
            self, "permission_history", "Water Chemistry Sample"
        )
        return permission_record.permission_allowed if permission_record else None

    @property
    def allow_datalogger_installation(self):
        """
        Returns the current permissions for the Thing.
        """
        permission_record = retrieve_latest_polymorphic_history_table_record(
            self, "permission_history", "Datalogger Installation"
        )
        return permission_record.permission_allowed if permission_record else None


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

    thing: Mapped["Thing"] = relationship("Thing", back_populates="links")


class WellScreen(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, discrete screened interval in a well.
    A Thing can have multiple WellScreens.
    """

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

    # --- Relationships ---
    # Many-To-One: A WellScreen belongs to one Thing.
    thing: Mapped["Thing"] = relationship("Thing", back_populates="screens")


class WellPurpose(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a controlled vocabulary term for well purposes.
    """

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = lexicon_term(nullable=False)

    search_vector: Mapped[TSVectorType] = mapped_column(TSVectorType("purpose"))

    thing: Mapped["Thing"] = relationship("Thing", back_populates="well_purposes")


class WellCasingMaterial(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a controlled vocabulary term for well casing materials.
    """

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    material: Mapped[str] = lexicon_term(nullable=False)

    search_vector: Mapped[TSVectorType] = mapped_column(TSVectorType("material"))

    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="well_casing_materials"
    )


class MonitoringFrequencyHistory(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents the monitoring frequency history for a Thing.
    """

    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    monitoring_frequency: Mapped[str] = lexicon_term(nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)

    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="monitoring_frequencies"
    )


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
