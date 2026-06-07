"""NM_Wells geothermal + drill-stem-test 1:1 staging mirror tables

Revision ID: v8w9x0y1z2a3
Revises: u7v8w9x0y1z2
Create Date: 2026-06-06 00:00:01.000000

1:1 staging mirror of the NM_Wells "Migrate First" Geothermal and Drill Stem
Test tables (see db/nmw_legacy.py and docs/nm_wells-migration.md). Columns and
lengths taken directly from the NM_Wells SQL dump DDL.

    Geothermal:
        tbl_gt_bht_headers     -> NMW_GtBhtHeaders
        tbl_gt_bht_data        -> NMW_GtBhtData
        tbl_ws_intervals       -> NMW_WsIntervals
        tbl_gt_conductivity    -> NMW_GtConductivity
        tbl_gt_heat_flow       -> NMW_GtHeatFlow
        tbl_gt_sum_heat_flow   -> NMW_GtSumHeatFlow
        tbl_gt_temp_depths     -> NMW_GtTempDepths
    Drill Stem Tests:
        tbl_ws_dst_headers     -> NMW_WsDstHeaders
        tbl_ws_dst_intervals   -> NMW_WsDstIntervals
        tbl_ws_dst_flow_history-> NMW_WsDstFlowHistory
        tbl_ws_dst_fluid_properties -> NMW_WsDstFluidProperties
        tbl_ws_dst_pressure    -> NMW_WsDstPressure
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "v8w9x0y1z2a3"
down_revision: Union[str, Sequence[str], None] = "u7v8w9x0y1z2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "NMW_GtBhtHeaders",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("BHTGUID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("BoreDia", sa.Float(), nullable=True),
        sa.Column("BoreUnits", sa.String(length=16), nullable=True),
        sa.Column("DrillFluid", sa.String(length=16), nullable=True),
        sa.Column("TempUnit", sa.String(length=1), nullable=True),
        sa.Column("FldSalinity", sa.Float(), nullable=True),
        sa.Column("FldRstvity", sa.Float(), nullable=True),
        sa.Column("Fluid_pH", sa.Float(), nullable=True),
        sa.Column("FldDensity", sa.Float(), nullable=True),
        sa.Column("FldLevel", sa.Float(), nullable=True),
        sa.Column("FldViscsty", sa.Float(), nullable=True),
        sa.Column("FluidLoss", sa.String(length=50), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("BHTGUID"),
    )
    op.create_index(
        "ix_NMW_GtBhtHeaders_SamplSetID", "NMW_GtBhtHeaders", ["SamplSetID"]
    )

    op.create_table(
        "NMW_GtBhtData",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("BHTGUID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Depth", sa.Float(), nullable=True),
        sa.Column("BHT", sa.Float(), nullable=True),
        sa.Column("TempUnit", sa.String(length=5), nullable=True),
        sa.Column("HrsSnceCir", sa.Float(), nullable=True),
        sa.Column("DateMeasrd", sa.DateTime(), nullable=True),
        sa.Column("Comments", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index("ix_NMW_GtBhtData_BHTGUID", "NMW_GtBhtData", ["BHTGUID"])

    op.create_table(
        "NMW_WsIntervals",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("IntrvlGUID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("SampleID", sa.String(length=128), nullable=True),
        sa.Column("From_Depth", sa.Float(), nullable=True),
        sa.Column("To_Depth", sa.Float(), nullable=True),
        sa.Column("From_TVD", sa.Float(), nullable=True),
        sa.Column("To_TVD", sa.Float(), nullable=True),
        sa.Column("From_Elev", sa.Float(), nullable=True),
        sa.Column("To_Elev", sa.Float(), nullable=True),
        sa.Column("Intv_Notes", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("IntrvlGUID"),
    )
    op.create_index("ix_NMW_WsIntervals_SamplSetID", "NMW_WsIntervals", ["SamplSetID"])

    op.create_table(
        "NMW_GtConductivity",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("IntrvlGUID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Cnductvity", sa.Float(), nullable=True),
        sa.Column("CnductUnit", sa.String(length=3), nullable=True),
        sa.Column("Comments", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_GtConductivity_IntrvlGUID", "NMW_GtConductivity", ["IntrvlGUID"]
    )

    op.create_table(
        "NMW_GtHeatFlow",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("IntrvlGUID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Gradient", sa.Float(), nullable=True),
        sa.Column("Ka", sa.Float(), nullable=True),
        sa.Column("Ka_unit", sa.String(length=3), nullable=True),
        sa.Column("Pm", sa.Float(), nullable=True),
        sa.Column("Kpr", sa.Float(), nullable=True),
        sa.Column("Kpr_unit", sa.String(length=3), nullable=True),
        sa.Column("Q", sa.Float(), nullable=True),
        sa.Column("Q_unit", sa.String(length=3), nullable=True),
        sa.Column("Comments", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index("ix_NMW_GtHeatFlow_IntrvlGUID", "NMW_GtHeatFlow", ["IntrvlGUID"])

    op.create_table(
        "NMW_GtSumHeatFlow",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("RecrdSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("LithClass", sa.String(length=50), nullable=True),
        sa.Column("UnitBasis", sa.String(length=16), nullable=True),
        sa.Column("UnitName", sa.String(length=128), nullable=True),
        sa.Column("GeoID", sa.String(length=16), nullable=True),
        sa.Column("FromDepth", sa.Float(), nullable=True),
        sa.Column("ToDepth", sa.Float(), nullable=True),
        sa.Column("DepthUnit", sa.String(length=8), nullable=True),
        sa.Column("From_Elev", sa.Float(), nullable=True),
        sa.Column("To_Elev", sa.Float(), nullable=True),
        sa.Column("ThermlGrad", sa.Float(), nullable=True),
        sa.Column("TGError", sa.Float(), nullable=True),
        sa.Column("GradUnit", sa.String(length=3), nullable=True),
        sa.Column("TGradRange", sa.String(length=15), nullable=True),
        sa.Column("SampleType", sa.String(length=50), nullable=True),
        sa.Column("NumSamples", sa.SmallInteger(), nullable=True),
        sa.Column("ThermlCond", sa.Float(), nullable=True),
        sa.Column("TCondError", sa.Float(), nullable=True),
        sa.Column("TCondUnit", sa.String(length=3), nullable=True),
        sa.Column("TCondRange", sa.String(length=15), nullable=True),
        sa.Column("HeatFlow", sa.Float(), nullable=True),
        sa.Column("HtFlowErr", sa.Float(), nullable=True),
        sa.Column("HtFlowUnit", sa.String(length=3), nullable=True),
        sa.Column("HtFlowEst", sa.Float(), nullable=True),
        sa.Column("Quality", sa.String(length=50), nullable=True),
        sa.Column("Comments", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_GtSumHeatFlow_RecrdSetID", "NMW_GtSumHeatFlow", ["RecrdSetID"]
    )
    op.create_index(
        "ix_NMW_GtSumHeatFlow_SamplSetID", "NMW_GtSumHeatFlow", ["SamplSetID"]
    )

    op.create_table(
        "NMW_GtTempDepths",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Depth", sa.Float(), nullable=True),
        sa.Column("Temp", sa.Float(), nullable=True),
        sa.Column("TempUnit", sa.String(length=1), nullable=True),
        sa.Column("IntrvlGrad", sa.Float(), nullable=True),
        sa.Column("Comments", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_GtTempDepths_SamplSetID", "NMW_GtTempDepths", ["SamplSetID"]
    )

    op.create_table(
        "NMW_WsDstHeaders",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("DSTGUID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("TestType", sa.String(length=50), nullable=True),
        sa.Column("DSTOprator", sa.String(length=50), nullable=True),
        sa.Column("PressUnits", sa.String(length=8), nullable=True),
        sa.Column("TempUnit", sa.String(length=1), nullable=True),
        sa.Column("PipeDiaUnt", sa.String(length=8), nullable=True),
        sa.Column("PipeLenUnt", sa.String(length=8), nullable=True),
        sa.Column("ChokeSizUn", sa.String(length=8), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("DSTGUID"),
    )
    op.create_index(
        "ix_NMW_WsDstHeaders_SamplSetID", "NMW_WsDstHeaders", ["SamplSetID"]
    )

    op.create_table(
        "NMW_WsDstIntervals",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("DSTInterval", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("DSTGUID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("DSTName", sa.String(length=128), nullable=True),
        sa.Column("TargetFm", sa.String(length=16), nullable=True),
        sa.Column("DSTDate", sa.DateTime(), nullable=True),
        sa.Column("DSTNumber", sa.SmallInteger(), nullable=True),
        sa.Column("Status", sa.String(length=255), nullable=True),
        sa.Column("StatusDate", sa.DateTime(), nullable=True),
        sa.Column("PackrFrom", sa.Float(), nullable=True),
        sa.Column("PackerTo", sa.Float(), nullable=True),
        sa.Column("SrfChokeSz", sa.Float(), nullable=True),
        sa.Column("BotChokeSz", sa.Float(), nullable=True),
        sa.Column("PipeDia", sa.Float(), nullable=True),
        sa.Column("PipeLength", sa.Float(), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("DSTInterval"),
    )
    op.create_index("ix_NMW_WsDstIntervals_DSTGUID", "NMW_WsDstIntervals", ["DSTGUID"])

    op.create_table(
        "NMW_WsDstFlowHistory",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("DSTInterval", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Operation", sa.String(length=255), nullable=True),
        sa.Column("StartTime", sa.DateTime(), nullable=True),
        sa.Column("EndTime", sa.DateTime(), nullable=True),
        sa.Column("Duration", sa.Float(), nullable=True),
        sa.Column("Pressure", sa.Float(), nullable=True),
        sa.Column("Temp", sa.Float(), nullable=True),
        sa.Column("RecovColmn", sa.Float(), nullable=True),
        sa.Column("RecovType", sa.String(length=255), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_WsDstFlowHistory_DSTInterval", "NMW_WsDstFlowHistory", ["DSTInterval"]
    )

    op.create_table(
        "NMW_WsDstFluidProperties",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("DSTInterval", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("SourceLoc", sa.String(length=255), nullable=True),
        sa.Column("Resistivty", sa.Float(), nullable=True),
        sa.Column("Temp", sa.Float(), nullable=True),
        sa.Column("Chlorides", sa.Float(), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_WsDstFluidProperties_DSTInterval",
        "NMW_WsDstFluidProperties",
        ["DSTInterval"],
    )

    op.create_table(
        "NMW_WsDstPressure",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("DSTInterval", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("PrsGageDpt", sa.Float(), nullable=True),
        sa.Column("BlankedOff", sa.SmallInteger(), nullable=True),
        sa.Column("InShtInMin", sa.Float(), nullable=True),
        sa.Column("FlwPrsInMin", sa.Float(), nullable=True),
        sa.Column("PrsInShtIn", sa.Float(), nullable=True),
        sa.Column("PrsInitClsdIn", sa.Float(), nullable=True),
        sa.Column("FnShtInMin", sa.Float(), nullable=True),
        sa.Column("FlwPrsFinMin", sa.Float(), nullable=True),
        sa.Column("PrsFnShtIn", sa.Float(), nullable=True),
        sa.Column("ShtInPrMth", sa.String(length=255), nullable=True),
        sa.Column("HydrostPrsIn", sa.Float(), nullable=True),
        sa.Column("HydStPrsFl", sa.Float(), nullable=True),
        sa.Column("HydstPrMth", sa.String(length=255), nullable=True),
        sa.Column("EquilPress", sa.Float(), nullable=True),
        sa.Column("EqlPrsMth", sa.String(length=255), nullable=True),
        sa.Column("FlowPrsMin", sa.Float(), nullable=True),
        sa.Column("FlowPrsMax", sa.Float(), nullable=True),
        sa.Column("FlowPrsMth", sa.String(length=255), nullable=True),
        sa.Column("DSTFluid", sa.String(length=128), nullable=True),
        sa.Column("FmTemp", sa.Float(), nullable=True),
        sa.Column("TempCorrtn", sa.Float(), nullable=True),
        sa.Column("TempFlowng", sa.Float(), nullable=True),
        sa.Column("TempUnit", sa.String(length=5), nullable=True),
        sa.Column("Notes", sa.String(length=255), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_WsDstPressure_DSTInterval", "NMW_WsDstPressure", ["DSTInterval"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_NMW_WsDstPressure_DSTInterval", table_name="NMW_WsDstPressure")
    op.drop_table("NMW_WsDstPressure")
    op.drop_index(
        "ix_NMW_WsDstFluidProperties_DSTInterval", table_name="NMW_WsDstFluidProperties"
    )
    op.drop_table("NMW_WsDstFluidProperties")
    op.drop_index(
        "ix_NMW_WsDstFlowHistory_DSTInterval", table_name="NMW_WsDstFlowHistory"
    )
    op.drop_table("NMW_WsDstFlowHistory")
    op.drop_index("ix_NMW_WsDstIntervals_DSTGUID", table_name="NMW_WsDstIntervals")
    op.drop_table("NMW_WsDstIntervals")
    op.drop_index("ix_NMW_WsDstHeaders_SamplSetID", table_name="NMW_WsDstHeaders")
    op.drop_table("NMW_WsDstHeaders")
    op.drop_index("ix_NMW_GtTempDepths_SamplSetID", table_name="NMW_GtTempDepths")
    op.drop_table("NMW_GtTempDepths")
    op.drop_index("ix_NMW_GtSumHeatFlow_RecrdSetID", table_name="NMW_GtSumHeatFlow")
    op.drop_index("ix_NMW_GtSumHeatFlow_SamplSetID", table_name="NMW_GtSumHeatFlow")
    op.drop_table("NMW_GtSumHeatFlow")
    op.drop_index("ix_NMW_GtHeatFlow_IntrvlGUID", table_name="NMW_GtHeatFlow")
    op.drop_table("NMW_GtHeatFlow")
    op.drop_index("ix_NMW_GtConductivity_IntrvlGUID", table_name="NMW_GtConductivity")
    op.drop_table("NMW_GtConductivity")
    op.drop_index("ix_NMW_WsIntervals_SamplSetID", table_name="NMW_WsIntervals")
    op.drop_table("NMW_WsIntervals")
    op.drop_index("ix_NMW_GtBhtData_BHTGUID", table_name="NMW_GtBhtData")
    op.drop_table("NMW_GtBhtData")
    op.drop_index("ix_NMW_GtBhtHeaders_SamplSetID", table_name="NMW_GtBhtHeaders")
    op.drop_table("NMW_GtBhtHeaders")
