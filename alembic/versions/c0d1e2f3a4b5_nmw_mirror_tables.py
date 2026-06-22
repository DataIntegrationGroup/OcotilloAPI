"""NMW staging mirror tables and FK constraints

Revision ID: c0d1e2f3a4b5
Revises: t6u7v8w9x0y1
Create Date: 2026-06-22

1:1 staging mirror of the legacy NM_Wells SQL Server tables needed for the
geothermal OGC collections (see db/nmw_legacy.py and docs/nm_wells-migration.md).
Faithful, column-for-column copies; the transform into the Ocotillo data model
is a later phase.

Core well tables:
    tbl_well_locations  -> NMW_WellLocations
    tbl_well_headers    -> NMW_WellHeaders
    tbl_well_records    -> NMW_WellRecords
    tbl_well_z_datum    -> NMW_WellZDatum
    tbl_well_samples    -> NMW_WellSamples

Geothermal tables:
    tbl_gt_bht_headers     -> NMW_GtBhtHeaders
    tbl_gt_bht_data        -> NMW_GtBhtData
    tbl_ws_intervals       -> NMW_WsIntervals
    tbl_gt_conductivity    -> NMW_GtConductivity
    tbl_gt_heat_flow       -> NMW_GtHeatFlow
    tbl_gt_sum_heat_flow   -> NMW_GtSumHeatFlow
    tbl_gt_temp_depths     -> NMW_GtTempDepths

Drill Stem Test tables:
    tbl_ws_dst_headers          -> NMW_WsDstHeaders
    tbl_ws_dst_intervals        -> NMW_WsDstIntervals
    tbl_ws_dst_flow_history     -> NMW_WsDstFlowHistory
    tbl_ws_dst_fluid_properties -> NMW_WsDstFluidProperties
    tbl_ws_dst_pressure         -> NMW_WsDstPressure

Publication/source registry:
    tbl_sources -> NMW_Sources
    (Keyed by free-text SourceID; joined into ogc_heat_flow for attribution.)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Core well tables
    # ------------------------------------------------------------------
    op.create_table(
        "NMW_WellLocations",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("WellDataID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Well_ID", sa.String(), nullable=True),
        sa.Column("Import_ID", sa.Integer(), nullable=True),
        sa.Column("Township", sa.Float(), nullable=True),
        sa.Column("NorS_TDir", sa.String(), nullable=True),
        sa.Column("Range", sa.Float(), nullable=True),
        sa.Column("EorW_RDir", sa.String(), nullable=True),
        sa.Column("Sectn", sa.SmallInteger(), nullable=True),
        sa.Column("SectnPart", sa.String(), nullable=True),
        sa.Column("UnitLetter", sa.String(), nullable=True),
        sa.Column("UTM_zone", sa.String(), nullable=True),
        sa.Column("State", sa.String(), nullable=True),
        sa.Column("County", sa.String(), nullable=True),
        sa.Column("Basin", sa.String(), nullable=True),
        sa.Column("Footage_NS", sa.Float(), nullable=True),
        sa.Column("NorS_FDir", sa.String(), nullable=True),
        sa.Column("Footage_EW", sa.Float(), nullable=True),
        sa.Column("EorW_FDir", sa.String(), nullable=True),
        sa.Column("Lat_min", sa.SmallInteger(), nullable=True),
        sa.Column("Lat_sec", sa.Float(), nullable=True),
        sa.Column("Long_deg", sa.SmallInteger(), nullable=True),
        sa.Column("Long_min", sa.SmallInteger(), nullable=True),
        sa.Column("Long_sec", sa.Float(), nullable=True),
        sa.Column("Lat_dd27", sa.Float(), nullable=True),
        sa.Column("Long_dd27", sa.Float(), nullable=True),
        sa.Column("Lat_dd83", sa.Float(), nullable=True),
        sa.Column("Long_dd83", sa.Float(), nullable=True),
        sa.Column("SourceID", sa.String(), nullable=True),
        sa.Column("SourceDatum", sa.String(), nullable=True),
        sa.Column("SourceUnits", sa.String(), nullable=True),
        sa.Column("LocAccType", sa.String(), nullable=True),
        sa.Column("LocAccMeas", sa.String(), nullable=True),
        sa.Column("LocAccVal", sa.Float(), nullable=True),
        sa.Column("Duplicated", sa.SmallInteger(), nullable=True),
        sa.Column("Exclude", sa.SmallInteger(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("API", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index(
        "ix_NMW_WellLocations_WellDataID", "NMW_WellLocations", ["WellDataID"]
    )

    op.create_table(
        "NMW_WellHeaders",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("WellDataID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("WellSpotID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("API", sa.String(), nullable=True),
        sa.Column("WellClass", sa.String(), nullable=True),
        sa.Column("WellType", sa.String(), nullable=True),
        sa.Column("WellOrient", sa.String(), nullable=True),
        sa.Column("CurWellNam", sa.String(), nullable=True),
        sa.Column("CurWellNum", sa.String(), nullable=True),
        sa.Column("CurStatus", sa.String(), nullable=True),
        sa.Column("PrdPoolCnt", sa.SmallInteger(), nullable=True),
        sa.Column("CurOperatr", sa.String(), nullable=True),
        sa.Column("CurOwner", sa.String(), nullable=True),
        sa.Column("TotalDepth", sa.Float(), nullable=True),
        sa.Column("Well_TVD", sa.Float(), nullable=True),
        sa.Column("Fm_TD", sa.String(), nullable=True),
        sa.Column("Age_TD", sa.String(), nullable=True),
        sa.Column("SpudDate", sa.DateTime(), nullable=True),
        sa.Column("ComplDate", sa.DateTime(), nullable=True),
        sa.Column("PlugDate", sa.DateTime(), nullable=True),
        sa.Column("PlugBack", sa.Float(), nullable=True),
        sa.Column("BridgePlug", sa.String(), nullable=True),
        sa.Column("ScoutTickt", sa.SmallInteger(), nullable=True),
        sa.Column("DwnHoleSur", sa.SmallInteger(), nullable=True),
        sa.Column("GeolLog", sa.SmallInteger(), nullable=True),
        sa.Column("Geophyslog", sa.SmallInteger(), nullable=True),
        sa.Column("GthrmExist", sa.SmallInteger(), nullable=True),
        sa.Column("PetroData", sa.SmallInteger(), nullable=True),
        sa.Column("CoreExists", sa.SmallInteger(), nullable=True),
        sa.Column("Cuttings", sa.SmallInteger(), nullable=True),
        sa.Column("SampleData", sa.SmallInteger(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.Column("Import_ID", sa.String(), nullable=True),
        sa.Column("Import_DB", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("WellDataID"),
    )

    op.create_table(
        "NMW_WellRecords",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("RecrdSetID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("WellDataID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("RecrdClass", sa.String(), nullable=True),
        sa.Column("SourceID", sa.String(), nullable=True),
        sa.Column("ActionDate", sa.DateTime(), nullable=True),
        sa.Column("WellName", sa.String(), nullable=True),
        sa.Column("WellNumber", sa.String(), nullable=True),
        sa.Column("API_suffix", sa.String(), nullable=True),
        sa.Column("EnteredBy", sa.String(), nullable=True),
        sa.Column("EntryDate", sa.DateTime(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("RecrdSetID"),
    )
    op.create_index("ix_NMW_WellRecords_WellDataID", "NMW_WellRecords", ["WellDataID"])

    op.create_table(
        "NMW_WellZDatum",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("RecrdsetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("Elev_GL", sa.Float(), nullable=True),
        sa.Column("Elev_DF", sa.Float(), nullable=True),
        sa.Column("Elev_KB", sa.Float(), nullable=True),
        sa.Column("Elev_unspc", sa.Float(), nullable=True),
        sa.Column("DatumElev", sa.Float(), nullable=True),
        sa.Column("DepthDatum", sa.String(), nullable=True),
        sa.Column("DepthUnits", sa.String(), nullable=True),
        sa.Column("Z_datum", sa.String(), nullable=True),
        sa.Column("Z_units", sa.String(), nullable=True),
        sa.Column("ElevSource", sa.String(), nullable=True),
        sa.Column("ElvAccType", sa.String(), nullable=True),
        sa.Column("ElvAccMeas", sa.String(), nullable=True),
        sa.Column("ElvAccVal", sa.Float(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.Column("GlobalID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index("ix_NMW_WellZDatum_RecrdsetID", "NMW_WellZDatum", ["RecrdsetID"])

    op.create_table(
        "NMW_WellSamples",
        sa.Column("OBJECTID", sa.Integer(), nullable=True),
        sa.Column("SamplSetID", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("RecrdsetID", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("SmpSetName", sa.String(), nullable=True),
        sa.Column("SamplClass", sa.String(), nullable=True),
        sa.Column("SampleType", sa.String(), nullable=True),
        sa.Column("SampleFm", sa.String(), nullable=True),
        sa.Column("SampleLoc", sa.String(), nullable=True),
        sa.Column("SampleDate", sa.DateTime(), nullable=True),
        sa.Column("From_Depth", sa.Float(), nullable=True),
        sa.Column("To_Depth", sa.Float(), nullable=True),
        sa.Column("SmpDpUnt", sa.String(), nullable=True),
        sa.Column("From_TVD", sa.Float(), nullable=True),
        sa.Column("To_TVD", sa.Float(), nullable=True),
        sa.Column("From_Elev", sa.Float(), nullable=True),
        sa.Column("To_Elev", sa.Float(), nullable=True),
        sa.Column("Porosity", sa.SmallInteger(), nullable=True),
        sa.Column("Permeablty", sa.SmallInteger(), nullable=True),
        sa.Column("Density", sa.SmallInteger(), nullable=True),
        sa.Column("DST_Tests", sa.SmallInteger(), nullable=True),
        sa.Column("ThinSect", sa.SmallInteger(), nullable=True),
        sa.Column("Geochron", sa.SmallInteger(), nullable=True),
        sa.Column("Geochem", sa.SmallInteger(), nullable=True),
        sa.Column("Geothermal", sa.SmallInteger(), nullable=True),
        sa.Column("WholeRock", sa.SmallInteger(), nullable=True),
        sa.Column("Paleontlgy", sa.SmallInteger(), nullable=True),
        sa.Column("EnteredBy", sa.String(), nullable=True),
        sa.Column("EntryDate", sa.DateTime(), nullable=True),
        sa.Column("Notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("SamplSetID"),
    )
    op.create_index("ix_NMW_WellSamples_RecrdsetID", "NMW_WellSamples", ["RecrdsetID"])

    # ------------------------------------------------------------------
    # Geothermal tables
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Drill Stem Test tables
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Publication/source registry
    # ------------------------------------------------------------------
    op.create_table(
        "NMW_Sources",
        sa.Column("OBJECTID", sa.Integer(), nullable=False),
        sa.Column("SourceID", sa.String(), nullable=True),
        sa.Column("FirstAuth", sa.String(), nullable=True),
        sa.Column("PubYear", sa.String(), nullable=True),
        sa.Column("Title", sa.String(), nullable=True),
        sa.Column("Journal", sa.String(), nullable=True),
        sa.Column("Volume", sa.String(), nullable=True),
        sa.Column("PageNo", sa.String(), nullable=True),
        sa.Column("ReportNo", sa.String(), nullable=True),
        sa.Column("Publisher", sa.String(), nullable=True),
        sa.Column("City", sa.String(), nullable=True),
        sa.Column("URL", sa.String(), nullable=True),
        sa.Column("Comments", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("OBJECTID"),
    )
    op.create_index("ix_NMW_Sources_SourceID", "NMW_Sources", ["SourceID"])

    # ------------------------------------------------------------------
    # FK constraints
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_nmw_welllocations_welldataid",
        "NMW_WellLocations",
        "NMW_WellHeaders",
        ["WellDataID"],
        ["WellDataID"],
    )
    op.create_foreign_key(
        "fk_nmw_wellrecords_welldataid",
        "NMW_WellRecords",
        "NMW_WellHeaders",
        ["WellDataID"],
        ["WellDataID"],
    )
    op.create_foreign_key(
        "fk_nmw_wellzdatum_recrdsetid",
        "NMW_WellZDatum",
        "NMW_WellRecords",
        ["RecrdsetID"],
        ["RecrdSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_wellsamples_recrdsetid",
        "NMW_WellSamples",
        "NMW_WellRecords",
        ["RecrdsetID"],
        ["RecrdSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtbhtheaders_samplsetid",
        "NMW_GtBhtHeaders",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtbhtdata_bhtguid",
        "NMW_GtBhtData",
        "NMW_GtBhtHeaders",
        ["BHTGUID"],
        ["BHTGUID"],
    )
    op.create_foreign_key(
        "fk_nmw_wsintervals_samplsetid",
        "NMW_WsIntervals",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtconductivity_intrvlguid",
        "NMW_GtConductivity",
        "NMW_WsIntervals",
        ["IntrvlGUID"],
        ["IntrvlGUID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtheatflow_intrvlguid",
        "NMW_GtHeatFlow",
        "NMW_WsIntervals",
        ["IntrvlGUID"],
        ["IntrvlGUID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtsumheatflow_recrdsetid",
        "NMW_GtSumHeatFlow",
        "NMW_WellRecords",
        ["RecrdSetID"],
        ["RecrdSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_gtsumheatflow_samplsetid",
        "NMW_GtSumHeatFlow",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_gttempdepths_samplsetid",
        "NMW_GtTempDepths",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_wsdstheaders_samplsetid",
        "NMW_WsDstHeaders",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    op.create_foreign_key(
        "fk_nmw_wsdstintervals_dstguid",
        "NMW_WsDstIntervals",
        "NMW_WsDstHeaders",
        ["DSTGUID"],
        ["DSTGUID"],
    )
    op.create_foreign_key(
        "fk_nmw_wsdstflowhistory_dstinterval",
        "NMW_WsDstFlowHistory",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )
    op.create_foreign_key(
        "fk_nmw_wsdstfluidproperties_dstinterval",
        "NMW_WsDstFluidProperties",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )
    op.create_foreign_key(
        "fk_nmw_wsdstpressure_dstinterval",
        "NMW_WsDstPressure",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )


def downgrade() -> None:
    # Drop FKs before tables (reverse order of creation)
    op.drop_constraint(
        "fk_nmw_wsdstpressure_dstinterval", "NMW_WsDstPressure", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wsdstfluidproperties_dstinterval",
        "NMW_WsDstFluidProperties",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_nmw_wsdstflowhistory_dstinterval",
        "NMW_WsDstFlowHistory",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_nmw_wsdstintervals_dstguid", "NMW_WsDstIntervals", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wsdstheaders_samplsetid", "NMW_WsDstHeaders", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_gttempdepths_samplsetid", "NMW_GtTempDepths", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_gtsumheatflow_samplsetid", "NMW_GtSumHeatFlow", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_gtsumheatflow_recrdsetid", "NMW_GtSumHeatFlow", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_gtheatflow_intrvlguid", "NMW_GtHeatFlow", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_gtconductivity_intrvlguid", "NMW_GtConductivity", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wsintervals_samplsetid", "NMW_WsIntervals", type_="foreignkey"
    )
    op.drop_constraint("fk_nmw_gtbhtdata_bhtguid", "NMW_GtBhtData", type_="foreignkey")
    op.drop_constraint(
        "fk_nmw_gtbhtheaders_samplsetid", "NMW_GtBhtHeaders", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wellsamples_recrdsetid", "NMW_WellSamples", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wellzdatum_recrdsetid", "NMW_WellZDatum", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_wellrecords_welldataid", "NMW_WellRecords", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_nmw_welllocations_welldataid", "NMW_WellLocations", type_="foreignkey"
    )

    # Drop tables in child-first order
    op.drop_index("ix_NMW_Sources_SourceID", table_name="NMW_Sources")
    op.drop_table("NMW_Sources")
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
    op.drop_index("ix_NMW_GtConductivity_IntrvlGUID", table_name="NMW_GtConductivity")
    op.drop_table("NMW_GtConductivity")
    op.drop_index("ix_NMW_GtHeatFlow_IntrvlGUID", table_name="NMW_GtHeatFlow")
    op.drop_table("NMW_GtHeatFlow")
    op.drop_index("ix_NMW_WsIntervals_SamplSetID", table_name="NMW_WsIntervals")
    op.drop_table("NMW_WsIntervals")
    op.drop_index("ix_NMW_GtBhtData_BHTGUID", table_name="NMW_GtBhtData")
    op.drop_table("NMW_GtBhtData")
    op.drop_index("ix_NMW_GtBhtHeaders_SamplSetID", table_name="NMW_GtBhtHeaders")
    op.drop_table("NMW_GtBhtHeaders")
    op.drop_index("ix_NMW_GtSumHeatFlow_SamplSetID", table_name="NMW_GtSumHeatFlow")
    op.drop_index("ix_NMW_GtSumHeatFlow_RecrdSetID", table_name="NMW_GtSumHeatFlow")
    op.drop_table("NMW_GtSumHeatFlow")
    op.drop_index("ix_NMW_GtTempDepths_SamplSetID", table_name="NMW_GtTempDepths")
    op.drop_table("NMW_GtTempDepths")
    op.drop_index("ix_NMW_WellSamples_RecrdsetID", table_name="NMW_WellSamples")
    op.drop_table("NMW_WellSamples")
    op.drop_index("ix_NMW_WellZDatum_RecrdsetID", table_name="NMW_WellZDatum")
    op.drop_table("NMW_WellZDatum")
    op.drop_index("ix_NMW_WellRecords_WellDataID", table_name="NMW_WellRecords")
    op.drop_table("NMW_WellRecords")
    op.drop_index("ix_NMW_WellLocations_WellDataID", table_name="NMW_WellLocations")
    op.drop_table("NMW_WellLocations")
    op.drop_table("NMW_WellHeaders")
