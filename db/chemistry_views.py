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
"""Read-only mappings over the legacy water-chemistry views.

`ogc_water_chemistry` and `ogc_internal_water_chemistry` are materialized views
built in d9e0f1a2b3c4 by unioning the four legacy NMA chemistry tables
(NMA_MajorChemistry, NMA_MinorTraceChemistry, NMA_Radionuclides,
NMA_FieldParameters) into one analyte-per-row shape. They were added for the OGC
EDR mount; these mappings let the REST API serve the same rows, which is where
the chemistry data actually lives -- the refactored `observation` table holds no
water chemistry.

Views only. Like db/ngwmn_views.py these use their own declarative base so
Alembic never tries to autogenerate a table for them, and the underlying
relations are refreshed by the migration that owns them, not from here.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ChemistryViewBase(DeclarativeBase):
    """Declarative base for chemistry view mappings, excluded from Alembic."""


class _WaterChemistryResultColumns:
    """Columns shared by the public and internal chemistry views.

    `id` is a text key (``maj-1``, ``min-2``, ``rad-3``, ``fld-4``) rather than
    an integer: a row's identity is which legacy table it came from plus that
    table's own id, and the four id sequences overlap.
    """

    id: Mapped[str] = mapped_column("id", String, primary_key=True)
    thing_id: Mapped[int] = mapped_column("thing_id", Integer)
    station_name: Mapped[str | None] = mapped_column("station_name", String)
    thing_type: Mapped[str | None] = mapped_column("thing_type", String)
    sample_id: Mapped[int | None] = mapped_column("sample_id", Integer)
    parameter_name: Mapped[str] = mapped_column("parameter_name", String)
    value: Mapped[float | None] = mapped_column("value", Float)
    unit: Mapped[str | None] = mapped_column("unit", String)
    # Named `datetime` in the view; exposed under the name the observation
    # endpoints already use so clients do not need a second field name.
    observation_datetime: Mapped[datetime] = mapped_column("datetime", DateTime)
    release_status: Mapped[str | None] = mapped_column("release_status", String)


class WaterChemistryResultsView(_WaterChemistryResultColumns, ChemistryViewBase):
    """Public chemistry analyses: released things, released samples."""

    __tablename__ = "ogc_water_chemistry"


class InternalWaterChemistryResultsView(
    _WaterChemistryResultColumns, ChemistryViewBase
):
    """Every chemistry analysis, including unreleased things and samples."""

    __tablename__ = "ogc_internal_water_chemistry"


# ============= EOF =============================================
