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
"""
Read-only ORM mappings over database views.

These models use their own declarative base, deliberately kept out of
``db.Base.metadata``: the views are created by hand-written Alembic
migrations, and registering them with the main metadata would make
autogenerate try to emit CREATE TABLE statements for them.

The primary keys declared here exist only to satisfy the ORM mapper.
Query individual columns (``session.query(Model.col, ...)``) rather than
full entities, so the identity map cannot silently collapse view rows
that happen to share a key.
"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ViewBase(DeclarativeBase):
    """Declarative base for view mappings, excluded from Alembic metadata."""


class NGWMNWaterLevels(ViewBase):
    """The NGWMN_WaterLevels view (manual groundwater level measurements)."""

    __tablename__ = "NGWMN_WaterLevels"

    point_id: Mapped[str] = mapped_column("PointID", String, primary_key=True)
    date_measured: Mapped[date] = mapped_column("DateMeasured", Date, primary_key=True)
    depth_to_water_bgs: Mapped[float | None] = mapped_column("DepthToWaterBGS", Float)
    wl_units: Mapped[str | None] = mapped_column("WLUnits", String)
    measurement_method: Mapped[str | None] = mapped_column("MeasurementMethod", String)
    wl_accuracy: Mapped[str | None] = mapped_column("WLAccuracy", String)
    public_release: Mapped[bool | None] = mapped_column("PublicRelease", Boolean)


class NGWMNWellConstruction(ViewBase):
    """The NGWMN_WellConstruction view (casing and screen intervals)."""

    __tablename__ = "NGWMN_WellConstruction"

    point_id: Mapped[str] = mapped_column("PointID", String, primary_key=True)
    casing_top: Mapped[float | None] = mapped_column(
        "CasingTop", Float, primary_key=True
    )
    casing_bottom: Mapped[float | None] = mapped_column("CasingBottom", Float)
    casing_depth_units: Mapped[str | None] = mapped_column("CasingDepthUnits", String)
    screen_top: Mapped[float | None] = mapped_column(
        "ScreenTop", Float, primary_key=True
    )
    screen_bottom: Mapped[float | None] = mapped_column("ScreenBottom", Float)
    screen_bottom_unit: Mapped[str | None] = mapped_column("ScreenBottomUnit", String)
    screen_description: Mapped[str | None] = mapped_column("ScreenDescription", String)
    casing_description: Mapped[str | None] = mapped_column("CasingDescription", String)


class NGWMNLithology(ViewBase):
    """The NGWMN_Lithology view (lithology intervals)."""

    __tablename__ = "NGWMN_Lithology"

    object_id: Mapped[int] = mapped_column("OBJECTID", Integer, primary_key=True)
    point_id: Mapped[str | None] = mapped_column("PointID", String)
    lithology: Mapped[str | None] = mapped_column("Lithology", String)
    term: Mapped[str | None] = mapped_column("TERM", String)
    strat_source: Mapped[str | None] = mapped_column("StratSource", String)
    strat_top: Mapped[float | None] = mapped_column("StratTop", Float)
    strat_top_unit: Mapped[str | None] = mapped_column("StratTopUnit", String)
    strat_bottom: Mapped[float | None] = mapped_column("StratBottom", Float)
    strat_bottom_unit: Mapped[str | None] = mapped_column("StratBottomUnit", String)


class TransducerDailyData(ViewBase):
    """
    The transducer_daily_data materialized view (daily aggregates of
    transducer observations per well, parameter, and QC status).
    """

    __tablename__ = "transducer_daily_data"

    thing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parameter_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date_measured: Mapped[date] = mapped_column(Date, primary_key=True)
    qced: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    point_id: Mapped[str | None] = mapped_column(String)
    parameter_name: Mapped[str | None] = mapped_column(String)
    depth_to_water_bgs: Mapped[float | None] = mapped_column(Float)
    depth_to_water_bgs_min: Mapped[float | None] = mapped_column(Float)
    depth_to_water_bgs_max: Mapped[float | None] = mapped_column(Float)
    measurement_count: Mapped[int | None] = mapped_column(BigInteger)
    first_measurement_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_measurement_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    temperature_water: Mapped[float | None] = mapped_column(Float)
    water_head: Mapped[float | None] = mapped_column(Float)
    water_head_adjusted: Mapped[float | None] = mapped_column(Float)
    conddl_ms_cm: Mapped[float | None] = mapped_column(Float)


# ============= EOF =============================================
