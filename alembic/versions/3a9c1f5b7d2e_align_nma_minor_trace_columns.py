"""Align NMA_MinorTraceChemistry columns with legacy schema.

Revision ID: 3a9c1f5b7d2e
Revises: c1d2e3f4a5b6
Create Date: 2026-01-31 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "3a9c1f5b7d2e"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Rename legacy columns and add missing fields."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_MinorTraceChemistry"):
        return

    table_name = "NMA_MinorTraceChemistry"
    columns = _column_names(inspector, table_name)

    rename_map = {
        "chemistry_sample_info_id": "SamplePtID",
        "sample_point_id": "SamplePointID",
        "analyte": "Analyte",
        "sample_value": "SampleValue",
        "units": "Units",
        "symbol": "Symbol",
        "analysis_method": "AnalysisMethod",
        "analysis_date": "AnalysisDate",
        "notes": "Notes",
        "analyses_agency": "AnalysesAgency",
        "uncertainty": "Uncertainty",
        "volume": "Volume",
        "volume_unit": "VolumeUnit",
    }

    for old_name, new_name in rename_map.items():
        if old_name in columns and new_name not in columns:
            op.alter_column(table_name, old_name, new_column_name=new_name)
            columns.remove(old_name)
            columns.add(new_name)

    if "SamplePointID" not in columns:
        op.add_column(
            table_name, sa.Column("SamplePointID", sa.String(length=10), nullable=True)
        )
    if "OBJECTID" not in columns:
        op.add_column(table_name, sa.Column("OBJECTID", sa.Integer(), nullable=True))
    if "WCLab_ID" not in columns:
        op.add_column(
            table_name, sa.Column("WCLab_ID", sa.String(length=25), nullable=True)
        )

    unique_constraints = inspector.get_unique_constraints(table_name)
    unique_columns = {tuple(uc.get("column_names") or []) for uc in unique_constraints}
    unique_names = {uc.get("name") for uc in unique_constraints}

    if (
        ("OBJECTID",) not in unique_columns
        and "uq_nma_minor_trace_chemistry_objectid" not in unique_names
    ):
        op.create_unique_constraint(
            "uq_nma_minor_trace_chemistry_objectid",
            table_name,
            ["OBJECTID"],
        )

    if "uq_minor_trace_chemistry_sample_analyte" not in unique_names:
        op.create_unique_constraint(
            "uq_minor_trace_chemistry_sample_analyte",
            table_name,
            ["SamplePtID", "Analyte"],
        )


def downgrade() -> None:
    """Revert column names and remove added fields."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("NMA_MinorTraceChemistry"):
        return

    table_name = "NMA_MinorTraceChemistry"
    columns = _column_names(inspector, table_name)

    unique_constraints = inspector.get_unique_constraints(table_name)
    unique_names = {uc.get("name") for uc in unique_constraints}

    if "uq_nma_minor_trace_chemistry_objectid" in unique_names:
        op.drop_constraint(
            "uq_nma_minor_trace_chemistry_objectid",
            table_name,
            type_="unique",
        )

    for column_name in ("WCLab_ID", "OBJECTID", "SamplePointID"):
        if column_name in columns:
            op.drop_column(table_name, column_name)

    rename_map = {
        "SamplePtID": "chemistry_sample_info_id",
        "Analyte": "analyte",
        "SampleValue": "sample_value",
        "Units": "units",
        "Symbol": "symbol",
        "AnalysisMethod": "analysis_method",
        "AnalysisDate": "analysis_date",
        "Notes": "notes",
        "AnalysesAgency": "analyses_agency",
        "Uncertainty": "uncertainty",
        "Volume": "volume",
        "VolumeUnit": "volume_unit",
    }

    columns = _column_names(inspector, table_name)
    for old_name, new_name in rename_map.items():
        if old_name in columns and new_name not in columns:
            op.alter_column(table_name, old_name, new_column_name=new_name)
            columns.remove(old_name)
            columns.add(new_name)
