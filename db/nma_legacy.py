# ===============================================================================
# Copyright 2026 ross
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

"""Legacy NM Aquifer models copied from AMPAPI.

This module contains models for NMA legacy tables that have been refactored to use
Integer primary keys. The original UUID PKs have been renamed with 'nma_' prefix
for audit/traceability purposes.

Refactoring Summary (UUID -> Integer PK):
- NMA_HydraulicsData: global_id -> nma_global_id, new id PK
- NMA_Stratigraphy: global_id -> nma_global_id, new id PK
- NMA_Chemistry_SampleInfo: sample_pt_id -> nma_sample_pt_id, new id PK
- NMA_AssociatedData: assoc_id -> nma_assoc_id, new id PK
- NMA_Radionuclides: global_id -> nma_global_id, new id PK
- NMA_MinorTraceChemistry: global_id -> nma_global_id, new id PK
- NMA_MajorChemistry: global_id -> nma_global_id, new id PK
- NMA_FieldParameters: global_id -> nma_global_id, new id PK

FK Standardization:
- Chemistry children now use chemistry_sample_info_id (Integer FK)
- Legacy UUID FKs stored as nma_sample_pt_id for audit

Legacy ID Columns Renamed (nma_ prefix):
- well_id -> nma_well_id
- point_id -> nma_point_id
- location_id -> nma_location_id
- object_id -> nma_object_id
- sample_point_id -> nma_sample_point_id
- wclab_id -> nma_wclab_id
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
    Identity,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from db.base import Base

if TYPE_CHECKING:
    from db.thing import Thing


class NMA_WaterLevelsContinuous_Pressure_Daily(Base):
    """
    Legacy view of the WaterLevelsContinuous_Pressure_Daily table from AMPAPI.

    This model is used for read-only migration/interop with the legacy NM Aquifer
    data and mirrors the original column names/types closely so transfer scripts
    can operate without further schema mapping.

    """

    __tablename__ = "NMA_WaterLevelsContinuous_Pressure_Daily"

    # PK
    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )

    # FK to Thing table - required for all WaterLevelsContinuous_Pressure_Daily records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK
    # Current `global_id` is also the original PK in the legacy DB

    # Legacy FK (not officially assigned as FK in legacy DB, but was used to link to wells)
    well_id: Mapped[Optional[uuid.UUID]] = mapped_column("WellID", UUID(as_uuid=True))

    # Additional columns
    object_id: Mapped[Optional[int]] = mapped_column(
        "OBJECTID", Integer, autoincrement=True
    )
    point_id: Mapped[Optional[str]] = mapped_column("PointID", String(50))
    date_measured: Mapped[datetime] = mapped_column(
        "DateMeasured", DateTime, nullable=False
    )
    temperature_water: Mapped[Optional[float]] = mapped_column(
        "TemperatureWater", Float
    )
    water_head: Mapped[Optional[float]] = mapped_column("WaterHead", Float)
    water_head_adjusted: Mapped[Optional[float]] = mapped_column(
        "WaterHeadAdjusted", Float
    )
    depth_to_water_bgs: Mapped[Optional[float]] = mapped_column(
        "DepthToWaterBGS", Float
    )
    measurement_method: Mapped[Optional[str]] = mapped_column(
        "MeasurementMethod", String(2)
    )
    data_source: Mapped[Optional[str]] = mapped_column("DataSource", String(5))
    measuring_agency: Mapped[Optional[str]] = mapped_column(
        "MeasuringAgency", String(50)
    )
    qced: Mapped[Optional[bool]] = mapped_column("QCed", Boolean)
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(100))
    created: Mapped[datetime] = mapped_column("Created", DateTime, nullable=False)
    updated: Mapped[datetime] = mapped_column("Updated", DateTime, nullable=False)
    processed_by: Mapped[Optional[str]] = mapped_column("ProcessedBy", String(4))
    checked_by: Mapped[Optional[str]] = mapped_column("CheckedBy", String(4))
    cond_dl_ms_cm: Mapped[Optional[float]] = mapped_column("CONDDL (mS/cm)", Float)

    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="pressure_daily_levels"
    )


class NMA_view_NGWMN_WellConstruction(Base):
    """
    Legacy NGWMN well construction view.

    A surrogate primary key is used so rows with missing depth values can still
    be represented faithfully from the legacy view.

    Note: This table is OUT OF SCOPE for refactoring (view table).
    """

    __tablename__ = "NMA_view_NGWMN_WellConstruction"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK
    # FK is undefined, but not needed for view tables such as this.

    # Legacy PK (for audit)
    # Legacy PK does not exist. This is expected for view tables such as this

    # Legacy FK (for audit)
    # Legacy FK does not exist. This is expected for view tables such as this.

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(50))
    casing_top: Mapped[Optional[float]] = mapped_column("CasingTop", Float)
    casing_bottom: Mapped[Optional[float]] = mapped_column("CasingBottom", Float)
    casing_depth_units: Mapped[Optional[str]] = mapped_column(
        "CasingDepthUnits", String(20)
    )
    screen_top: Mapped[Optional[float]] = mapped_column("ScreenTop", Float)
    screen_bottom: Mapped[Optional[float]] = mapped_column("ScreenBottom", Float)
    screen_bottom_unit: Mapped[Optional[str]] = mapped_column(
        "ScreenBottomUnit", String(20)
    )
    screen_description: Mapped[Optional[str]] = mapped_column(
        "ScreenDescription", String(250)
    )
    casing_description: Mapped[Optional[str]] = mapped_column(
        "CasingDescription", String(250)
    )


class NMA_view_NGWMN_WaterLevels(Base):
    """
    Legacy NGWMN water levels view.

    Note: This table is OUT OF SCOPE for refactoring (view table).
    """

    __tablename__ = "NMA_view_NGWMN_WaterLevels"

    # PK
    point_id: Mapped[str] = mapped_column("PointID", String(50), primary_key=True)
    date_measured: Mapped[date] = mapped_column("DateMeasured", Date, primary_key=True)

    # FK
    # FK is undefined, but not needed for view tables such as this.

    # Legacy PK (for audit)
    # Legacy PK does not exist. This is expected for view tables such as this

    # Legacy FK (for audit)
    # Legacy FK does not exist. This is expected for view tables such as this.

    # Additional columns
    depth_to_water_bgs: Mapped[Optional[float]] = mapped_column(
        "DepthToWaterBGS", Float
    )
    wl_units: Mapped[Optional[str]] = mapped_column("WLUnits", String(10))
    measurement_method: Mapped[Optional[str]] = mapped_column(
        "MeasurementMethod", String(50)
    )
    wl_accuracy: Mapped[Optional[float]] = mapped_column("WLAccuracy", Float)
    public_release: Mapped[Optional[bool]] = mapped_column("PublicRelease", Boolean)


class NMA_view_NGWMN_Lithology(Base):
    """
    Legacy NGWMN lithology view.

    Note: This table is OUT OF SCOPE for refactoring (view table).
    """

    __tablename__ = "NMA_view_NGWMN_Lithology"

    # PK
    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)

    # FK
    # FK is undefined, but not needed for view tables such as this.

    # Legacy PK (for audit)
    # Legacy PK does not exist. This is expected for view tables such as this

    # Legacy FK (for audit)
    # Legacy FK does not exist. This is expected for view tables such as this.

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(50))
    lithology: Mapped[Optional[str]] = mapped_column("Lithology", String(50))
    term: Mapped[Optional[str]] = mapped_column("TERM", String(100))
    strat_source: Mapped[Optional[str]] = mapped_column("StratSource", String(100))
    strat_top: Mapped[Optional[float]] = mapped_column("StratTop", Float)
    strat_top_unit: Mapped[Optional[str]] = mapped_column("StratTopUnit", String(20))
    strat_bottom: Mapped[Optional[float]] = mapped_column("StratBottom", Float)
    strat_bottom_unit: Mapped[Optional[str]] = mapped_column(
        "StratBottomUnit", String(20)
    )


class NMA_HydraulicsData(Base):
    """
    Legacy HydraulicsData table from AMPAPI.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - nma_well_id: Legacy WellID UUID
    - nma_point_id: Legacy PointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    """

    __tablename__ = "NMA_HydraulicsData"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to Thing - required for all HydraulicsData records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_well_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_WellID", UUID(as_uuid=True)
    )

    # Additional columns
    nma_point_id: Mapped[Optional[str]] = mapped_column("nma_PointID", String(50))
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    data_source: Mapped[Optional[str]] = mapped_column("Data Source", String(255))
    cs_gal_d_ft: Mapped[Optional[float]] = mapped_column("Cs (gal/d/ft)", Float)
    hd_ft2_d: Mapped[Optional[float]] = mapped_column("HD (ft2/d)", Float)
    hl_day_1: Mapped[Optional[float]] = mapped_column("HL (day-1)", Float)
    kh_ft_d: Mapped[Optional[float]] = mapped_column("KH (ft/d)", Float)
    kv_ft_d: Mapped[Optional[float]] = mapped_column("KV (ft/d)", Float)
    p_decimal_fraction: Mapped[Optional[float]] = mapped_column(
        "P (decimal fraction)", Float
    )
    s_dimensionless: Mapped[Optional[float]] = mapped_column("S (dimensionless)", Float)
    ss_ft_1: Mapped[Optional[float]] = mapped_column("Ss (ft-1)", Float)
    sy_decimalfractn: Mapped[Optional[float]] = mapped_column(
        "Sy (decimalfractn)", Float
    )
    t_ft2_d: Mapped[Optional[float]] = mapped_column("T (ft2/d)", Float)
    k_darcy: Mapped[Optional[float]] = mapped_column("k (darcy)", Float)

    test_bottom: Mapped[int] = mapped_column("TestBottom", SmallInteger, nullable=False)
    test_top: Mapped[int] = mapped_column("TestTop", SmallInteger, nullable=False)
    hydraulic_unit: Mapped[Optional[str]] = mapped_column("HydraulicUnit", String(18))
    hydraulic_unit_type: Mapped[Optional[str]] = mapped_column(
        "HydraulicUnitType", String(2)
    )
    hydraulic_remarks: Mapped[Optional[str]] = mapped_column(
        "Hydraulic Remarks", String(200)
    )

    # Relationships
    thing: Mapped["Thing"] = relationship("Thing", back_populates="hydraulics_data")

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_HydraulicsData - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_HydraulicsData requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_Stratigraphy(Base):
    """
    Legacy stratigraphy (lithology log) data from AMPAPI.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - nma_well_id: Legacy WellID UUID
    - nma_point_id: Legacy PointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    """

    __tablename__ = "NMA_Stratigraphy"
    __table_args__ = (
        CheckConstraint(
            'char_length("nma_PointID") > 0',
            name="ck_nma_stratigraphy_pointid_len",
        ),
    )

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to Thing table - required for all Stratigraphy records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_well_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_WellID", UUID(as_uuid=True)
    )

    # Additional columns
    nma_point_id: Mapped[str] = mapped_column("nma_PointID", String(10), nullable=False)
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    strat_top: Mapped[int] = mapped_column("StratTop", SmallInteger, nullable=False)
    strat_bottom: Mapped[int] = mapped_column(
        "StratBottom", SmallInteger, nullable=False
    )
    unit_identifier: Mapped[Optional[str]] = mapped_column("UnitIdentifier", String(20))
    lithology: Mapped[Optional[str]] = mapped_column("Lithology", String(4))
    lithologic_modifier: Mapped[Optional[str]] = mapped_column(
        "LithologicModifier", String(255)
    )
    contributing_unit: Mapped[Optional[str]] = mapped_column(
        "ContributingUnit", String(2)
    )
    strat_source: Mapped[Optional[str]] = mapped_column("StratSource", Text)
    strat_notes: Mapped[Optional[str]] = mapped_column("StratNotes", Text)

    thing: Mapped["Thing"] = relationship("Thing", back_populates="stratigraphy_logs")

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_Stratigraphy - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_Stratigraphy requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_Chemistry_SampleInfo(Base):
    """
    Legacy Chemistry SampleInfo table from AMPAPI.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_sample_pt_id: Original UUID PK (SamplePtID), now UNIQUE for audit
    - nma_wclab_id: Legacy WCLab_ID
    - nma_sample_point_id: Legacy SamplePointID
    - nma_object_id: Legacy OBJECTID, UNIQUE
    - nma_location_id: Legacy LocationId UUID (for audit trail)

    FK to Thing:
    - thing_id: Integer FK to Thing.id
    - Linked via nma_SamplePointID matching Thing.name during transfer
    """

    __tablename__ = "NMA_Chemistry_SampleInfo"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to Thing - required for all ChemistrySampleInfo records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    nma_sample_pt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_SamplePtID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_LocationId", UUID(as_uuid=True)
    )

    # Additional columns
    nma_wclab_id: Mapped[Optional[str]] = mapped_column("nma_WCLab_ID", String(18))
    nma_sample_point_id: Mapped[str] = mapped_column(
        "nma_SamplePointID", String(10), nullable=False
    )
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    collection_date: Mapped[Optional[datetime]] = mapped_column(
        "CollectionDate", DateTime
    )
    collection_method: Mapped[Optional[str]] = mapped_column(
        "CollectionMethod", String(50)
    )
    collected_by: Mapped[Optional[str]] = mapped_column("CollectedBy", String(5))
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))

    sample_type: Mapped[Optional[str]] = mapped_column("SampleType", String(50))
    sample_material_not_h2o: Mapped[Optional[str]] = mapped_column(
        "SampleMaterialNotH2O", String(100)
    )
    water_type: Mapped[Optional[str]] = mapped_column("WaterType", String(50))
    study_sample: Mapped[Optional[str]] = mapped_column("StudySample", Text)

    data_source: Mapped[Optional[str]] = mapped_column("DataSource", String(100))
    data_quality: Mapped[Optional[bool]] = mapped_column(
        "DataQuality", Boolean, server_default=text("true")
    )
    public_release: Mapped[Optional[bool]] = mapped_column("PublicRelease", Boolean)

    added_day_to_date: Mapped[Optional[bool]] = mapped_column("AddedDaytoDate", Boolean)
    added_month_day_to_date: Mapped[Optional[bool]] = mapped_column(
        "AddedMonthDaytoDate", Boolean
    )
    sample_notes: Mapped[Optional[str]] = mapped_column("SampleNotes", Text)

    # --- Relationships ---
    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="chemistry_sample_infos"
    )

    minor_trace_chemistries: Mapped[List["NMA_MinorTraceChemistry"]] = relationship(
        "NMA_MinorTraceChemistry",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    radionuclides: Mapped[List["NMA_Radionuclides"]] = relationship(
        "NMA_Radionuclides",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    major_chemistries: Mapped[List["NMA_MajorChemistry"]] = relationship(
        "NMA_MajorChemistry",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    field_parameters: Mapped[List["NMA_FieldParameters"]] = relationship(
        "NMA_FieldParameters",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan ChemistrySampleInfo - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "ChemistrySampleInfo requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_AssociatedData(Base):
    """
    Legacy AssociatedData table from NM_Aquifer.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_assoc_id: Original UUID PK (AssocID), now UNIQUE for audit
    - nma_location_id: Legacy LocationId UUID, UNIQUE
    - nma_point_id: Legacy PointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    """

    __tablename__ = "NMA_AssociatedData"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to Thing - required for all AssociatedData records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    nma_assoc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_AssocID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_LocationId", UUID(as_uuid=True), unique=True
    )

    # Additional columns
    nma_point_id: Mapped[Optional[str]] = mapped_column("nma_PointID", String(10))
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(255))
    formation: Mapped[Optional[str]] = mapped_column("Formation", String(15))

    # Relationships
    thing: Mapped["Thing"] = relationship("Thing", back_populates="associated_data")

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_AssociatedData - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_AssociatedData requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_SurfaceWaterData(Base):
    """
    Legacy SurfaceWaterData table from AMPAPI.

    Note: This table is a Thing child (linked via LocationId -> Thing.nma_pk_location).
    """

    __tablename__ = "NMA_SurfaceWaterData"

    # PK
    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)

    # FK
    # FK to Thing - required for all SurfaceWaterData records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    surface_id: Mapped[uuid.UUID] = mapped_column(
        "SurfaceID", UUID(as_uuid=True), nullable=False, unique=True
    )

    # Legacy FK (for audit)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "LocationId", UUID(as_uuid=True)
    )

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(10))
    discharge: Mapped[Optional[str]] = mapped_column("Discharge", String(50))
    discharge_method: Mapped[Optional[str]] = mapped_column(
        "DischargeMethod", String(50)
    )
    discharge_rate: Mapped[Optional[float]] = mapped_column("DischargeRate", Float)
    discharge_units: Mapped[Optional[str]] = mapped_column("DischargeUnits", String(3))
    date_measured: Mapped[Optional[datetime]] = mapped_column("DateMeasured", DateTime)
    discharge_source: Mapped[Optional[str]] = mapped_column(
        "DischargeSource", String(50)
    )
    site_notes: Mapped[Optional[str]] = mapped_column("SiteNotes", String(200))
    field_method_notes: Mapped[Optional[str]] = mapped_column(
        "FieldMethodNotes", String(200)
    )
    formation_zone: Mapped[Optional[str]] = mapped_column("FormationZone", String(15))
    aq_class: Mapped[Optional[str]] = mapped_column("AqClass", String(50))
    source_notes: Mapped[Optional[str]] = mapped_column("SourceNotes", String(200))
    data_source: Mapped[Optional[str]] = mapped_column("DataSource", String(255))

    # Relationships
    thing: Mapped["Thing"] = relationship("Thing", back_populates="surface_water_data")
    surface_water_photos: Mapped[list["NMA_SurfaceWaterPhotos"]] = relationship(
        "NMA_SurfaceWaterPhotos",
        back_populates="surface_water_data",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_SurfaceWaterData - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_SurfaceWaterData requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_SurfaceWaterPhotos(Base):
    """
    Legacy SurfaceWaterPhotos table from NM_Aquifer.

    Note: This table is a child of NMA_SurfaceWaterData via SurfaceID.
    """

    __tablename__ = "NMA_SurfaceWaterPhotos"

    # PK
    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )

    # FK
    surface_id: Mapped[uuid.UUID] = mapped_column(
        "SurfaceID",
        UUID(as_uuid=True),
        ForeignKey("NMA_SurfaceWaterData.SurfaceID", ondelete="CASCADE"),
        nullable=False,
    )

    # Legacy PK (for audit)
    # Current `global_id` is also the original PK in the legacy DB

    # Legacy FK (for audit)
    # surface_id is also the legacy FK in the source table.

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(50), nullable=False)
    ole_path: Mapped[Optional[str]] = mapped_column("OLEPath", String(50))
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)

    # Relationships
    surface_water_data: Mapped["NMA_SurfaceWaterData"] = relationship(
        "NMA_SurfaceWaterData", back_populates="surface_water_photos"
    )

    @validates("surface_id")
    def validate_surface_id(self, key, value):
        """Prevent orphan NMA_SurfaceWaterPhotos - must have a parent NMA_SurfaceWaterData."""
        if value is None:
            raise ValueError(
                "NMA_SurfaceWaterPhotos requires a parent NMA_SurfaceWaterData "
                "(surface_id cannot be None)"
            )
        return value


class NMA_WeatherData(Base):
    """
    Legacy WeatherData table from AMPAPI.

    Note: This table is a Thing child and must link to a parent Thing.
    """

    __tablename__ = "NMA_WeatherData"

    # PK
    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)

    # FK
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    weather_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "WeatherID", UUID(as_uuid=True)
    )

    # Legacy FK (for audit)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "LocationId", UUID(as_uuid=True)
    )

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(10))

    # Relationships
    thing: Mapped["Thing"] = relationship("Thing", back_populates="weather_data")

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_WeatherData - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_WeatherData requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_WeatherPhotos(Base):
    """
    Legacy WeatherPhotos table from NM_Aquifer.

    Note: This table is OUT OF SCOPE for refactoring (not a Thing child).
    """

    __tablename__ = "NMA_WeatherPhotos"

    # PK:
    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )

    # FK:
    # FK not assigned.

    # Legacy PK (for audit):
    # Current `global_id` is also the original PK in the legacy DB

    # Legacy FK (for audit):
    weather_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "WeatherID", UUID(as_uuid=True)
    )

    # Additional columns
    point_id: Mapped[str] = mapped_column("PointID", String(50), nullable=False)
    ole_path: Mapped[Optional[str]] = mapped_column("OLEPath", String(50))
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)


class NMA_Soil_Rock_Results(Base):
    """
    Legacy Soil_Rock_Results table from NM_Aquifer.

    Already has Integer PK. Only legacy column renames needed:
    - point_id -> nma_point_id
    """

    __tablename__ = "NMA_Soil_Rock_Results"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to Thing
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # Legacy PK (for audit)
    # Legacy PK does not exist.

    # Legacy FK (for audit) (not officially assigned as FK in legacy DB, but was used to link to wells)
    nma_point_id: Mapped[Optional[str]] = mapped_column("nma_Point_ID", String(255))

    # Additional columns
    sample_type: Mapped[Optional[str]] = mapped_column("Sample Type", String(255))
    date_sampled: Mapped[Optional[str]] = mapped_column("Date Sampled", String(255))
    d13c: Mapped[Optional[float]] = mapped_column("d13C", Float)
    d18o: Mapped[Optional[float]] = mapped_column("d18O", Float)
    sampled_by: Mapped[Optional[str]] = mapped_column("Sampled by", String(255))

    # Relationships
    thing: Mapped["Thing"] = relationship("Thing", back_populates="soil_rock_results")

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        """Prevent orphan NMA_Soil_Rock_Results - must have a parent Thing."""
        if value is None:
            raise ValueError(
                "NMA_Soil_Rock_Results requires a parent Thing (thing_id cannot be None)"
            )
        return value


class NMA_MinorTraceChemistry(Base):
    """
    Legacy MinorandTraceChemistry table from AMPAPI.

    Stores minor and trace element chemistry results linked to a ChemistrySampleInfo.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
    - nma_chemistry_sample_info_uuid: Legacy UUID FK for audit
    - nma_wclab_id: Legacy WCLab_ID string (audit)
    """

    __tablename__ = "NMA_MinorTraceChemistry"
    __table_args__ = (
        UniqueConstraint(
            "chemistry_sample_info_id",
            "analyte",
            name="uq_minor_trace_chemistry_sample_analyte",
        ),
    )

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to ChemistrySampleInfo table - required for all MinorTraceChemistry records
    chemistry_sample_info_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("NMA_Chemistry_SampleInfo.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_chemistry_sample_info_uuid: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_chemistry_sample_info_uuid", UUID(as_uuid=True), nullable=True
    )

    # Additional columns
    analyte: Mapped[Optional[str]] = mapped_column("analyte", String(50))
    symbol: Mapped[Optional[str]] = mapped_column("symbol", String(10))
    sample_value: Mapped[Optional[float]] = mapped_column("sample_value", Float)
    units: Mapped[Optional[str]] = mapped_column("units", String(20))
    uncertainty: Mapped[Optional[float]] = mapped_column("uncertainty", Float)
    analysis_method: Mapped[Optional[str]] = mapped_column(
        "analysis_method", String(100)
    )
    analysis_date: Mapped[Optional[date]] = mapped_column("analysis_date", Date)
    notes: Mapped[Optional[str]] = mapped_column("notes", Text)
    volume: Mapped[Optional[int]] = mapped_column("volume", Integer)
    volume_unit: Mapped[Optional[str]] = mapped_column("volume_unit", String(20))
    analyses_agency: Mapped[Optional[str]] = mapped_column(
        "analyses_agency", String(100)
    )
    nma_wclab_id: Mapped[Optional[str]] = mapped_column("nma_WCLab_ID", String(25))

    # --- Relationships ---
    chemistry_sample_info: Mapped["NMA_Chemistry_SampleInfo"] = relationship(
        "NMA_Chemistry_SampleInfo", back_populates="minor_trace_chemistries"
    )

    @validates("chemistry_sample_info_id")
    def validate_chemistry_sample_info_id(self, key, value):
        if value is None:
            raise ValueError(
                "NMA_MinorTraceChemistry requires a chemistry_sample_info_id"
            )
        return value


class NMA_Radionuclides(Base):
    """
    Legacy Radionuclides table from NM_Aquifer_Dev_DB.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
    - nma_sample_pt_id: Legacy UUID FK (SamplePtID) for audit
    - nma_sample_point_id: Legacy SamplePointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    - nma_wclab_id: Legacy WCLab_ID
    """

    __tablename__ = "NMA_Radionuclides"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to ChemistrySampleInfo table - required for all Radionuclides records
    chemistry_sample_info_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("NMA_Chemistry_SampleInfo.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_sample_pt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_SamplePtID", UUID(as_uuid=True), nullable=True
    )

    # Additional columns
    nma_sample_point_id: Mapped[Optional[str]] = mapped_column(
        "nma_SamplePointID", String(10)
    )
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    nma_wclab_id: Mapped[Optional[str]] = mapped_column("nma_WCLab_ID", String(25))
    analyte: Mapped[Optional[str]] = mapped_column("Analyte", String(50))
    symbol: Mapped[Optional[str]] = mapped_column("Symbol", String(50))
    sample_value: Mapped[Optional[float]] = mapped_column(
        "SampleValue", Float, server_default=text("0")
    )
    units: Mapped[Optional[str]] = mapped_column("Units", String(50))
    uncertainty: Mapped[Optional[float]] = mapped_column(
        "Uncertainty", Float, server_default=text("0")
    )
    analysis_method: Mapped[Optional[str]] = mapped_column(
        "AnalysisMethod", String(255)
    )
    analysis_date: Mapped[Optional[datetime]] = mapped_column("AnalysisDate", DateTime)
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(255))
    volume: Mapped[Optional[int]] = mapped_column(
        "Volume", Integer, server_default=text("0")
    )
    volume_unit: Mapped[Optional[str]] = mapped_column("VolumeUnit", String(50))
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))

    # Relationships
    chemistry_sample_info: Mapped["NMA_Chemistry_SampleInfo"] = relationship(
        "NMA_Chemistry_SampleInfo", back_populates="radionuclides"
    )

    @validates("chemistry_sample_info_id")
    def validate_chemistry_sample_info_id(self, key, value):
        if value is None:
            raise ValueError("NMA_Radionuclides requires a chemistry_sample_info_id")
        return value


class NMA_MajorChemistry(Base):
    """
    Legacy MajorChemistry table from NM_Aquifer_Dev_DB.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
    - nma_sample_pt_id: Legacy UUID FK (SamplePtID) for audit
    - nma_sample_point_id: Legacy SamplePointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    - nma_wclab_id: Legacy WCLab_ID
    """

    __tablename__ = "NMA_MajorChemistry"

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to ChemistrySampleInfo table - required for all MajorChemistry records
    chemistry_sample_info_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("NMA_Chemistry_SampleInfo.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_sample_pt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_SamplePtID", UUID(as_uuid=True), nullable=True
    )

    # Additional columns
    nma_sample_point_id: Mapped[Optional[str]] = mapped_column(
        "nma_SamplePointID", String(10)
    )
    nma_object_id: Mapped[Optional[int]] = mapped_column(
        "nma_OBJECTID", Integer, unique=True
    )
    nma_wclab_id: Mapped[Optional[str]] = mapped_column("nma_WCLab_ID", String(25))
    analyte: Mapped[Optional[str]] = mapped_column("Analyte", String(50))
    symbol: Mapped[Optional[str]] = mapped_column("Symbol", String(50))
    sample_value: Mapped[Optional[float]] = mapped_column(
        "SampleValue", Float, server_default=text("0")
    )
    units: Mapped[Optional[str]] = mapped_column("Units", String(50))
    uncertainty: Mapped[Optional[float]] = mapped_column("Uncertainty", Float)
    analysis_method: Mapped[Optional[str]] = mapped_column(
        "AnalysisMethod", String(255)
    )
    analysis_date: Mapped[Optional[datetime]] = mapped_column("AnalysisDate", DateTime)
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(255))
    volume: Mapped[Optional[int]] = mapped_column(
        "Volume", Integer, server_default=text("0")
    )
    volume_unit: Mapped[Optional[str]] = mapped_column("VolumeUnit", String(50))
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))

    # Relationships
    chemistry_sample_info: Mapped["NMA_Chemistry_SampleInfo"] = relationship(
        "NMA_Chemistry_SampleInfo", back_populates="major_chemistries"
    )

    @validates("chemistry_sample_info_id")
    def validate_chemistry_sample_info_id(self, key, value):
        if value is None:
            raise ValueError("NMA_MajorChemistry requires a chemistry_sample_info_id")
        return value


class NMA_FieldParameters(Base):
    """
    Legacy FieldParameters table from AMPAPI.
    Stores field measurements (pH, Temp, etc.) linked to ChemistrySampleInfo.

    Refactored from UUID PK to Integer PK:
    - id: Integer PK (autoincrement)
    - nma_global_id: Original UUID PK, now UNIQUE for audit
    - chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
    - nma_sample_pt_id: Legacy UUID FK (SamplePtID) for audit
    - nma_sample_point_id: Legacy SamplePointID string
    - nma_object_id: Legacy OBJECTID, UNIQUE
    - nma_wclab_id: Legacy WCLab_ID
    """

    __tablename__ = "NMA_FieldParameters"

    __table_args__ = (
        # Explicit Indexes (updated for new column names)
        Index("FieldParameters$AnalysesAgency", "AnalysesAgency"),
        Index(
            "FieldParameters$ChemistrySampleInfoFieldParameters",
            "chemistry_sample_info_id",
        ),
        Index("FieldParameters$FieldParameter", "FieldParameter"),
        Index("FieldParameters$nma_SamplePointID", "nma_SamplePointID"),
        Index("FieldParameters$nma_WCLab_ID", "nma_WCLab_ID"),
        # Unique Indexes
        Index("FieldParameters$nma_GlobalID", "nma_GlobalID", unique=True),
        Index("FieldParameters$nma_OBJECTID", "nma_OBJECTID", unique=True),
    )

    # PK
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK to ChemistrySampleInfo table - required for all FieldParameters records
    chemistry_sample_info_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "NMA_Chemistry_SampleInfo.id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Legacy PK (for audit)
    nma_global_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_GlobalID", UUID(as_uuid=True), unique=True, nullable=True
    )

    # Legacy FK (for audit)
    nma_sample_pt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "nma_SamplePtID", UUID(as_uuid=True), nullable=True
    )

    # Additional columns
    nma_sample_point_id: Mapped[Optional[str]] = mapped_column(
        "nma_SamplePointID", String(10)
    )
    nma_object_id: Mapped[int] = mapped_column(
        "nma_OBJECTID", Integer, Identity(start=1), nullable=False
    )
    nma_wclab_id: Mapped[Optional[str]] = mapped_column("nma_WCLab_ID", String(25))
    field_parameter: Mapped[Optional[str]] = mapped_column("FieldParameter", String(50))
    sample_value: Mapped[Optional[float]] = mapped_column(
        "SampleValue", Float, nullable=True
    )
    units: Mapped[Optional[str]] = mapped_column("Units", String(50))
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(255))
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))

    # Relationships
    chemistry_sample_info: Mapped["NMA_Chemistry_SampleInfo"] = relationship(
        "NMA_Chemistry_SampleInfo", back_populates="field_parameters"
    )

    @validates("chemistry_sample_info_id")
    def validate_chemistry_sample_info_id(self, key, value):
        if value is None:
            raise ValueError(
                "FieldParameter requires a parent ChemistrySampleInfo (chemistry_sample_info_id)"
            )
        return value


# ============= EOF =============================================
