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
"""Create minor_trace_chemistry table.

Revision ID: d0f94b0b93a2
Revises: 8ed4b9770721
Create Date: 2026-01-08

Migrates MinorandTraceChemistry table from NMAquifer.
Columns migrated: AnalysesAgency, Analyte, Symbol, SampleValue, Units,
Uncertainty, AnalysisMethod, AnalysisDate, Notes, Volume, VolumeUnit.
Columns excluded: GlobalID, OBJECTID, SSMA_TimeStamp, SamplePointID,
SamplePtID, WCLab_ID.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "d0f94b0b93a2"
down_revision: Union[str, Sequence[str], None] = "8ed4b9770721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create minor_trace_chemistry table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("minor_trace_chemistry"):
        op.create_table(
            "minor_trace_chemistry",
            # Primary key from AutoBaseMixin
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            # Audit columns from AuditMixin (via AutoBaseMixin)
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("timezone('UTC', now())"),
            ),
            sa.Column("created_by_name", sa.String(length=255), nullable=True),
            sa.Column("created_by_id", sa.String(length=255), nullable=True),
            sa.Column("updated_by_name", sa.String(length=255), nullable=True),
            sa.Column("updated_by_id", sa.String(length=255), nullable=True),
            # Release status from ReleaseMixin
            sa.Column(
                "release_status",
                sa.String(length=100),
                sa.ForeignKey("lexicon_term.term", onupdate="CASCADE"),
                nullable=True,
                default="draft",
            ),
            # Migrated columns from NMAquifer MinorandTraceChemistry
            sa.Column("analyses_agency", sa.String(length=50), nullable=True),
            sa.Column("analyte", sa.String(length=50), nullable=True),
            sa.Column("symbol", sa.String(length=50), nullable=True),
            sa.Column("sample_value", sa.Float(), nullable=True),
            sa.Column("units", sa.String(length=50), nullable=True),
            sa.Column("uncertainty", sa.Float(), nullable=True),
            sa.Column("analysis_method", sa.String(length=255), nullable=True),
            sa.Column("analysis_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.String(length=255), nullable=True),
            sa.Column("volume", sa.Integer(), nullable=True),
            sa.Column("volume_unit", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    """Drop minor_trace_chemistry table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("minor_trace_chemistry"):
        op.drop_table("minor_trace_chemistry")
