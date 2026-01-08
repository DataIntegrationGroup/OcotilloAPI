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

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, SmallInteger, String
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
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


class NMAHydraulicsData(Base):
    """
    Legacy HydraulicsData table from AMPAPI.
    """

    __tablename__ = "NMA_HydraulicsData"

    global_id: Mapped[str] = mapped_column("GlobalID", String(40), primary_key=True)
    point_id: Mapped[Optional[str]] = mapped_column("PointID", String(50))
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


class ChemistrySampleInfo(Base):
    """
    Legacy Chemistry SampleInfo table from AMPAPI.
    """

    __tablename__ = "NMA_Chemistry_SampleInfo"

    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)
    sample_point_id: Mapped[Optional[str]] = mapped_column("SamplePointID", String(50))
    sample_pt_id: Mapped[Optional[str]] = mapped_column("SamplePtID", String(50))
    wclab_id: Mapped[Optional[str]] = mapped_column("WCLab_ID", String(50))

    collection_date: Mapped[Optional[date]] = mapped_column("CollectionDate", Date)
    collection_method: Mapped[Optional[str]] = mapped_column(
        "CollectionMethod", String(100)
    )
    collected_by: Mapped[Optional[str]] = mapped_column("CollectedBy", String(100))
    analyses_agency: Mapped[Optional[str]] = mapped_column(
        "AnalysesAgency", String(100)
    )

    sample_type: Mapped[Optional[str]] = mapped_column("SampleType", String(100))
    sample_material_not_h2o: Mapped[Optional[bool]] = mapped_column(
        "SampleMaterialNotH2O", Boolean
    )
    water_type: Mapped[Optional[str]] = mapped_column("WaterType", String(100))
    study_sample: Mapped[Optional[bool]] = mapped_column("StudySample", Boolean)

    data_source: Mapped[Optional[str]] = mapped_column("DataSource", String(100))
    data_quality: Mapped[Optional[str]] = mapped_column("DataQuality", String(100))
    public_release: Mapped[Optional[bool]] = mapped_column("PublicRelease", Boolean)

    added_day_to_date: Mapped[Optional[str]] = mapped_column(
        "AddedDaytoDate", String(10)
    )
    added_month_day_to_date: Mapped[Optional[str]] = mapped_column(
        "AddedMonthDaytoDate", String(10)
    )
    sample_notes: Mapped[Optional[str]] = mapped_column("SampleNotes", Text)


# ============= EOF =============================================
