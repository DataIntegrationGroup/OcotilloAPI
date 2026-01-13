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
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


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
        "SamplePointID", String(10), nullable=False, unique=True
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


# ============= EOF =============================================
