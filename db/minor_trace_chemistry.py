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
"""
Minor and Trace Chemistry model for storing minor and trace element chemistry data
migrated from NMAquifer MinorandTraceChemistry table.

Migrated columns (excluding GlobalID, OBJECTID, SSMA_TimeStamp, SamplePointID,
SamplePtID, WCLab_ID):
- AnalysesAgency -> analyses_agency
- Analyte -> analyte
- Symbol -> symbol (detect flag indicator)
- SampleValue -> sample_value
- Units -> units
- Uncertainty -> uncertainty
- AnalysisMethod -> analysis_method
- AnalysisDate -> analysis_date
- Notes -> notes
- Volume -> volume
- VolumeUnit -> volume_unit
"""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    Float,
    String,
)
from sqlalchemy.orm import mapped_column, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin


class MinorTraceChemistry(Base, AutoBaseMixin, ReleaseMixin):
    """
    Minor and Trace Chemistry data model.

    This table stores minor and trace element chemistry measurements migrated
    from the NMAquifer MinorandTraceChemistry table.
    """

    # --- Columns migrated from NMAquifer MinorandTraceChemistry ---

    analyses_agency: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Agency that performed the analyses (e.g., 'NMBGMR')",
    )

    analyte: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="The analyte code/name being measured (e.g., 'As', 'U', 'Fe')",
    )

    symbol: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Detection flag symbol (e.g., '<' for below detection limit)",
    )

    sample_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="The measured value for the analyte",
    )

    units: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Units of measurement (e.g., 'mg/L', 'ug/L')",
    )

    uncertainty: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Measurement uncertainty value",
    )

    analysis_method: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Method used for analysis (e.g., 'ICP-MS', 'ICP-OES')",
    )

    analysis_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Date and time when the analysis was performed",
    )

    notes: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Additional notes about the measurement",
    )

    volume: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Sample volume",
    )

    volume_unit: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Units for sample volume (e.g., 'mL')",
    )


# ============= EOF =============================================
