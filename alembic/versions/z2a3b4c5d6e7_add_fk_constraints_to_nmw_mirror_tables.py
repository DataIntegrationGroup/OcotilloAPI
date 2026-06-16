"""add FK constraints to NMW staging mirror tables

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-06-15

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WellLocations -> WellHeaders
    op.create_foreign_key(
        "fk_nmw_welllocations_welldataid",
        "NMW_WellLocations",
        "NMW_WellHeaders",
        ["WellDataID"],
        ["WellDataID"],
    )
    # WellRecords -> WellHeaders
    op.create_foreign_key(
        "fk_nmw_wellrecords_welldataid",
        "NMW_WellRecords",
        "NMW_WellHeaders",
        ["WellDataID"],
        ["WellDataID"],
    )
    # WellZDatum -> WellRecords
    op.create_foreign_key(
        "fk_nmw_wellzdatum_recrdsetid",
        "NMW_WellZDatum",
        "NMW_WellRecords",
        ["RecrdsetID"],
        ["RecrdSetID"],
    )
    # WellSamples -> WellRecords
    op.create_foreign_key(
        "fk_nmw_wellsamples_recrdsetid",
        "NMW_WellSamples",
        "NMW_WellRecords",
        ["RecrdsetID"],
        ["RecrdSetID"],
    )
    # GtBhtHeaders -> WellSamples
    op.create_foreign_key(
        "fk_nmw_gtbhtheaders_samplsetid",
        "NMW_GtBhtHeaders",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    # GtBhtData -> GtBhtHeaders
    op.create_foreign_key(
        "fk_nmw_gtbhtdata_bhtguid",
        "NMW_GtBhtData",
        "NMW_GtBhtHeaders",
        ["BHTGUID"],
        ["BHTGUID"],
    )
    # WsIntervals -> WellSamples
    op.create_foreign_key(
        "fk_nmw_wsintervals_samplsetid",
        "NMW_WsIntervals",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    # GtConductivity -> WsIntervals
    op.create_foreign_key(
        "fk_nmw_gtconductivity_intrvlguid",
        "NMW_GtConductivity",
        "NMW_WsIntervals",
        ["IntrvlGUID"],
        ["IntrvlGUID"],
    )
    # GtHeatFlow -> WsIntervals
    op.create_foreign_key(
        "fk_nmw_gtheatflow_intrvlguid",
        "NMW_GtHeatFlow",
        "NMW_WsIntervals",
        ["IntrvlGUID"],
        ["IntrvlGUID"],
    )
    # GtSumHeatFlow -> WellRecords
    op.create_foreign_key(
        "fk_nmw_gtsumheatflow_recrdsetid",
        "NMW_GtSumHeatFlow",
        "NMW_WellRecords",
        ["RecrdSetID"],
        ["RecrdSetID"],
    )
    # GtSumHeatFlow -> WellSamples
    op.create_foreign_key(
        "fk_nmw_gtsumheatflow_samplsetid",
        "NMW_GtSumHeatFlow",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    # GtTempDepths -> WellSamples
    op.create_foreign_key(
        "fk_nmw_gttempdepths_samplsetid",
        "NMW_GtTempDepths",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    # WsDstHeaders -> WellSamples
    op.create_foreign_key(
        "fk_nmw_wsdstheaders_samplsetid",
        "NMW_WsDstHeaders",
        "NMW_WellSamples",
        ["SamplSetID"],
        ["SamplSetID"],
    )
    # WsDstIntervals -> WsDstHeaders
    op.create_foreign_key(
        "fk_nmw_wsdstintervals_dstguid",
        "NMW_WsDstIntervals",
        "NMW_WsDstHeaders",
        ["DSTGUID"],
        ["DSTGUID"],
    )
    # WsDstFlowHistory -> WsDstIntervals
    op.create_foreign_key(
        "fk_nmw_wsdstflowhistory_dstinterval",
        "NMW_WsDstFlowHistory",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )
    # WsDstFluidProperties -> WsDstIntervals
    op.create_foreign_key(
        "fk_nmw_wsdstfluidproperties_dstinterval",
        "NMW_WsDstFluidProperties",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )
    # WsDstPressure -> WsDstIntervals
    op.create_foreign_key(
        "fk_nmw_wsdstpressure_dstinterval",
        "NMW_WsDstPressure",
        "NMW_WsDstIntervals",
        ["DSTInterval"],
        ["DSTInterval"],
    )


def downgrade() -> None:
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
