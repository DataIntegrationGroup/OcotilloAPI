"""NM_Wells 1:1 staging mirror tables

Revision ID: u7v8w9x0y1z2
Revises: t6u7v8w9x0y1
Create Date: 2026-06-06 00:00:00.000000

1:1 staging mirror of the legacy NM_Wells SQL Server "Migrate First / Main"
tables (see db/nmw_legacy.py and docs/nm_wells-migration.md). Faithful,
column-for-column copies; the transform into the Ocotillo data model is a
later phase.

    tbl_well_locations -> NMW_WellLocations
    tbl_well_headers   -> NMW_WellHeaders
    tbl_well_records   -> NMW_WellRecords
    tbl_well_z_datum   -> NMW_WellZDatum
    tbl_well_samples   -> NMW_WellSamples
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "u7v8w9x0y1z2"
down_revision: Union[str, Sequence[str], None] = "t6u7v8w9x0y1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_NMW_WellSamples_RecrdsetID", table_name="NMW_WellSamples")
    op.drop_table("NMW_WellSamples")
    op.drop_index("ix_NMW_WellZDatum_RecrdsetID", table_name="NMW_WellZDatum")
    op.drop_table("NMW_WellZDatum")
    op.drop_index("ix_NMW_WellRecords_WellDataID", table_name="NMW_WellRecords")
    op.drop_table("NMW_WellRecords")
    op.drop_table("NMW_WellHeaders")
    op.drop_index("ix_NMW_WellLocations_WellDataID", table_name="NMW_WellLocations")
    op.drop_table("NMW_WellLocations")
