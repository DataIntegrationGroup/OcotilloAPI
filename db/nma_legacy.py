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

"""Legacy NM Aquifer models copied from AMPAPI."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from db.base import Base
from sqlalchemy import (
    Boolean,
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

if TYPE_CHECKING:
    from db.thing import Thing


class NMAWaterLevelsContinuousPressureDaily(Base):
    """
    Legacy view of the WaterLevelsContinuous_Pressure_Daily table from AMPAPI.

    This model is used for read-only migration/interop with the legacy NM Aquifer
    data and mirrors the original column names/types closely so transfer scripts
    can operate without further schema mapping.
    """

    __tablename__ = "NMA_WaterLevelsContinuous_Pressure_Daily"

    global_id: Mapped[str] = mapped_column("GlobalID", String(40), primary_key=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        "OBJECTID", Integer, autoincrement=True
    )
    well_id: Mapped[Optional[str]] = mapped_column("WellID", String(40))
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


class ViewNGWMNWellConstruction(Base):
    """
    Legacy NGWMN well construction view.

    A surrogate primary key is used so rows with missing depth values can still
    be represented faithfully from the legacy view.
    """

    __tablename__ = "NMA_view_NGWMN_WellConstruction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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


class ViewNGWMNWaterLevels(Base):
    """
    Legacy NGWMN water levels view.
    """

    __tablename__ = "NMA_view_NGWMN_WaterLevels"

    point_id: Mapped[str] = mapped_column("PointID", String(50), primary_key=True)
    date_measured: Mapped[date] = mapped_column("DateMeasured", Date, primary_key=True)
    depth_to_water_bgs: Mapped[Optional[float]] = mapped_column(
        "DepthToWaterBGS", Float
    )
    wl_units: Mapped[Optional[str]] = mapped_column("WLUnits", String(10))
    measurement_method: Mapped[Optional[str]] = mapped_column(
        "MeasurementMethod", String(50)
    )
    wl_accuracy: Mapped[Optional[float]] = mapped_column("WLAccuracy", Float)
    public_release: Mapped[Optional[bool]] = mapped_column("PublicRelease", Boolean)


class ViewNGWMNLithology(Base):
    """
    Legacy NGWMN lithology view.
    """

    __tablename__ = "NMA_view_NGWMN_Lithology"

    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)
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


class NMAHydraulicsData(Base):
    """
    Legacy HydraulicsData table from AMPAPI.
    """

    __tablename__ = "NMA_HydraulicsData"

    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )
    well_id: Mapped[Optional[uuid.UUID]] = mapped_column("WellID", UUID(as_uuid=True))
    point_id: Mapped[Optional[str]] = mapped_column("PointID", String(50))
    data_source: Mapped[Optional[str]] = mapped_column("Data Source", String(255))
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)

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

    thing: Mapped["Thing"] = relationship("Thing")


class Stratigraphy(Base):
    """Legacy stratigraphy (lithology log) data from AMPAPI."""

    __tablename__ = "NMA_Stratigraphy"

    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )
    well_id: Mapped[Optional[uuid.UUID]] = mapped_column("WellID", UUID(as_uuid=True))
    point_id: Mapped[str] = mapped_column("PointID", String(10), nullable=False)
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    strat_top: Mapped[Optional[float]] = mapped_column("StratTop", Float)
    strat_bottom: Mapped[Optional[float]] = mapped_column("StratBottom", Float)
    unit_identifier: Mapped[Optional[str]] = mapped_column("UnitIdentifier", String(50))
    lithology: Mapped[Optional[str]] = mapped_column("Lithology", String(100))
    lithologic_modifier: Mapped[Optional[str]] = mapped_column(
        "LithologicModifier", String(100)
    )
    contributing_unit: Mapped[Optional[str]] = mapped_column(
        "ContributingUnit", String(10)
    )
    strat_source: Mapped[Optional[str]] = mapped_column("StratSource", Text)
    strat_notes: Mapped[Optional[str]] = mapped_column("StratNotes", Text)
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)

    thing: Mapped["Thing"] = relationship("Thing", back_populates="stratigraphy_logs")


class ChemistrySampleInfo(Base):
    """
    Legacy Chemistry SampleInfo table from AMPAPI.
    """

    __tablename__ = "NMA_Chemistry_SampleInfo"

    sample_pt_id: Mapped[uuid.UUID] = mapped_column(
        "SamplePtID", UUID(as_uuid=True), primary_key=True
    )
    wclab_id: Mapped[Optional[str]] = mapped_column("WCLab_ID", String(18))
    sample_point_id: Mapped[str] = mapped_column(
        "SamplePointID", String(10), nullable=False
    )

    # FK to Thing - required for all ChemistrySampleInfo records
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
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

    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "LocationId", UUID(as_uuid=True)
    )

    # --- Relationships ---
    thing: Mapped["Thing"] = relationship(
        "Thing", back_populates="chemistry_sample_infos"
    )

    minor_trace_chemistries: Mapped[List["NMAMinorTraceChemistry"]] = relationship(
        "NMAMinorTraceChemistry",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    radionuclides: Mapped[List["NMARadionuclides"]] = relationship(
        "NMARadionuclides",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    major_chemistries: Mapped[List["NMAMajorChemistry"]] = relationship(
        "NMAMajorChemistry",
        back_populates="chemistry_sample_info",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    field_parameters: Mapped[List["NMAFieldParameters"]] = relationship(
        "NMAFieldParameters",
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


class SurfaceWaterData(Base):
    """
    Legacy SurfaceWaterData table from AMPAPI.
    """

    __tablename__ = "NMA_SurfaceWaterData"

    surface_id: Mapped[uuid.UUID] = mapped_column(
        "SurfaceID", UUID(as_uuid=True), nullable=False
    )
    point_id: Mapped[str] = mapped_column("PointID", String(10))
    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)

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


class WeatherData(Base):
    """
    Legacy WeatherData table from AMPAPI.
    """

    __tablename__ = "NMA_WeatherData"

    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "LocationId", UUID(as_uuid=True)
    )
    point_id: Mapped[str] = mapped_column("PointID", String(10))
    weather_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "WeatherID", UUID(as_uuid=True)
    )
    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)


class NMAMinorTraceChemistry(Base):
    """
    Legacy MinorandTraceChemistry table from AMPAPI.

    Stores minor and trace element chemistry results linked to a ChemistrySampleInfo.
    """

    __tablename__ = "NMA_MinorTraceChemistry"
    __table_args__ = (
        UniqueConstraint(
            "chemistry_sample_info_id",
            "analyte",
            name="uq_minor_trace_chemistry_sample_analyte",
        ),
    )

    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )

    # FK to ChemistrySampleInfo - required (no orphans)
    chemistry_sample_info_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("NMA_Chemistry_SampleInfo.SamplePtID", ondelete="CASCADE"),
        nullable=False,
    )

    # Legacy columns
    analyte: Mapped[Optional[str]] = mapped_column(String(50))
    sample_value: Mapped[Optional[float]] = mapped_column(Float)
    units: Mapped[Optional[str]] = mapped_column(String(20))
    symbol: Mapped[Optional[str]] = mapped_column(String(10))
    analysis_method: Mapped[Optional[str]] = mapped_column(String(100))
    analysis_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    analyses_agency: Mapped[Optional[str]] = mapped_column(String(100))
    uncertainty: Mapped[Optional[float]] = mapped_column(Float)
    volume: Mapped[Optional[float]] = mapped_column(Float)
    volume_unit: Mapped[Optional[str]] = mapped_column(String(20))

    # --- Relationships ---
    chemistry_sample_info: Mapped["ChemistrySampleInfo"] = relationship(
        "ChemistrySampleInfo", back_populates="minor_trace_chemistries"
    )

    @validates("chemistry_sample_info_id")
    def validate_chemistry_sample_info_id(self, key, value):
        """Prevent orphan NMAMinorTraceChemistry - must have a parent ChemistrySampleInfo."""
        if value is None:
            raise ValueError(
                "NMAMinorTraceChemistry requires a parent ChemistrySampleInfo"
            )
        return value


class NMARadionuclides(Base):
    """
    Legacy Radionuclides table from NM_Aquifer_Dev_DB.
    """

    __tablename__ = "NMA_Radionuclides"

    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )
    sample_pt_id: Mapped[uuid.UUID] = mapped_column(
        "SamplePtID",
        UUID(as_uuid=True),
        ForeignKey("NMA_Chemistry_SampleInfo.SamplePtID", ondelete="CASCADE"),
        nullable=False,
    )
    sample_point_id: Mapped[Optional[str]] = mapped_column("SamplePointID", String(10))
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
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))
    wclab_id: Mapped[Optional[str]] = mapped_column("WCLab_ID", String(25))

    thing: Mapped["Thing"] = relationship("Thing")
    chemistry_sample_info: Mapped["ChemistrySampleInfo"] = relationship(
        "ChemistrySampleInfo", back_populates="radionuclides"
    )

    @validates("thing_id")
    def validate_thing_id(self, key, value):
        if value is None:
            raise ValueError(
                "NMARadionuclides requires a Thing (thing_id cannot be None)"
            )
        return value

    @validates("sample_pt_id")
    def validate_sample_pt_id(self, key, value):
        if value is None:
            raise ValueError("NMARadionuclides requires a SamplePtID")
        return value


class NMAMajorChemistry(Base):
    """
    Legacy MajorChemistry table from NM_Aquifer_Dev_DB.
    """

    __tablename__ = "NMA_MajorChemistry"

    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True
    )
    sample_pt_id: Mapped[uuid.UUID] = mapped_column(
        "SamplePtID",
        UUID(as_uuid=True),
        ForeignKey("NMA_Chemistry_SampleInfo.SamplePtID", ondelete="CASCADE"),
        nullable=False,
    )
    sample_point_id: Mapped[Optional[str]] = mapped_column("SamplePointID", String(10))
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
    object_id: Mapped[Optional[int]] = mapped_column("OBJECTID", Integer, unique=True)
    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))
    wclab_id: Mapped[Optional[str]] = mapped_column("WCLab_ID", String(25))

    chemistry_sample_info: Mapped["ChemistrySampleInfo"] = relationship(
        "ChemistrySampleInfo", back_populates="major_chemistries"
    )

    @validates("sample_pt_id")
    def validate_sample_pt_id(self, key, value):
        if value is None:
            raise ValueError("NMAMajorChemistry requires a SamplePtID")
        return value


class NMAFieldParameters(Base):
    """
    Legacy FieldParameters table from AMPAPI.
    Stores field measurements (pH, Temp, etc.) linked to ChemistrySampleInfo.
    """

    __tablename__ = "NMA_FieldParameters"

    __table_args__ = (
        # Explicit Indexes from DDL
        Index("FieldParameters$AnalysesAgency", "AnalysesAgency"),
        Index("FieldParameters$ChemistrySampleInfoFieldParameters", "SamplePtID"),
        Index("FieldParameters$FieldParameter", "FieldParameter"),
        Index("FieldParameters$SamplePointID", "SamplePointID"),
        Index(
            "FieldParameters$SamplePtID", "SamplePtID"
        ),  # Note: DDL had two indexes on this col
        Index("FieldParameters$WCLab_ID", "WCLab_ID"),
        # Unique Indexes (Explicitly named to match DDL)
        Index("FieldParameters$GlobalID", "GlobalID", unique=True),
        Index("FieldParameters$OBJECTID", "OBJECTID", unique=True),
    )

    # Primary Key
    global_id: Mapped[uuid.UUID] = mapped_column(
        "GlobalID", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign Key
    sample_pt_id: Mapped[uuid.UUID] = mapped_column(
        "SamplePtID",
        UUID(as_uuid=True),
        ForeignKey(
            "NMA_Chemistry_SampleInfo.SamplePtID",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Legacy Columns
    sample_point_id: Mapped[Optional[str]] = mapped_column("SamplePointID", String(10))
    field_parameter: Mapped[Optional[str]] = mapped_column("FieldParameter", String(50))
    sample_value: Mapped[float] = mapped_column(
        "SampleValue", Float, server_default="0"
    )
    units: Mapped[Optional[str]] = mapped_column("Units", String(50))
    notes: Mapped[Optional[str]] = mapped_column("Notes", String(255))

    # Identity Column
    object_id: Mapped[int] = mapped_column(
        "OBJECTID", Integer, Identity(start=1), nullable=False
    )

    analyses_agency: Mapped[Optional[str]] = mapped_column("AnalysesAgency", String(50))
    wc_lab_id: Mapped[Optional[str]] = mapped_column("WCLab_ID", String(25))

    # Relationships
    chemistry_sample_info: Mapped["ChemistrySampleInfo"] = relationship(
        "ChemistrySampleInfo", back_populates="field_parameters"
    )

    @validates("sample_pt_id")
    def validate_sample_pt_id(self, key, value):
        if value is None:
            raise ValueError(
                "FieldParameter requires a parent ChemistrySampleInfo (SamplePtID)"
            )
        return value


# ============= EOF =============================================
