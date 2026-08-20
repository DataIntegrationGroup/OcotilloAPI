"""CM_legacy staging mirror tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-20

1:1 staging mirror of the McLemore critical-minerals chemistry workbook
(Earth MRI, NMBGMR; see db/cm_legacy.py and
docs/critical-minerals-legacy-mirror.md). Faithful copies of the workbook
sheets; the transform into the Ocotillo data model is a later phase.

    ChemicalData / GIS / QAQC -> CM_ChemicalData  (source_sheet discriminator)
    DetectionLimits           -> CM_DetectionLimits
    References                -> CM_References
    MineralSystems            -> CM_MineralSystems
    world                     -> CM_WorldComparisons
    world_ref                 -> CM_WorldReferences
    General Information / MetaData / DefinitionOfFields
                              -> CM_WorkbookMetadata

Every data column is a String: the workbook stores censored analyte values as
text ("<0.1"), carries Excel error text ("#VALUE!"), and mixes dates with free
text. Parsing belongs to the transform.

The ChemicalData, GIS and QAQC sheets disagree with each other and none is
authoritative, so all three are mirrored and reconciliation is deferred. See
the module docstring in db/cm_legacy.py.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "CM_ChemicalData",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_sheet", sa.String(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("sample", sa.String(), nullable=True),
        sa.Column("project", sa.String(), nullable=True),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("date_collected", sa.String(), nullable=True),
        sa.Column("date_analyzed", sa.String(), nullable=True),
        sa.Column("chem_lab_file_no", sa.String(), nullable=True),
        sa.Column("laboratory", sa.String(), nullable=True),
        sa.Column("latitude", sa.String(), nullable=True),
        sa.Column("longitude", sa.String(), nullable=True),
        sa.Column("coordinate_system", sa.String(), nullable=True),
        sa.Column("county", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("lithology", sa.String(), nullable=True),
        sa.Column("mineral_system", sa.String(), nullable=True),
        sa.Column("deposit_types", sa.String(), nullable=True),
        sa.Column("map_symbol", sa.String(), nullable=True),
        sa.Column("method_collected", sa.String(), nullable=True),
        sa.Column("sample_source", sa.String(), nullable=True),
        sa.Column("mineralogy_deposit_type", sa.String(), nullable=True),
        sa.Column("depth_legnth_ft", sa.String(), nullable=True),
        sa.Column("mine_id", sa.String(), nullable=True),
        sa.Column("location_notes", sa.String(), nullable=True),
        sa.Column("comments", sa.String(), nullable=True),
        sa.Column("paste_ph", sa.String(), nullable=True),
        sa.Column("paste_conductivity", sa.String(), nullable=True),
        sa.Column("tds_mg_l", sa.String(), nullable=True),
        sa.Column("sio2_pct", sa.String(), nullable=True),
        sa.Column("tio2_pct", sa.String(), nullable=True),
        sa.Column("al2o3_pct", sa.String(), nullable=True),
        sa.Column("fe2o3t_pct", sa.String(), nullable=True),
        sa.Column("mno_pct", sa.String(), nullable=True),
        sa.Column("mgo_pct", sa.String(), nullable=True),
        sa.Column("cao_pct", sa.String(), nullable=True),
        sa.Column("na2o_pct", sa.String(), nullable=True),
        sa.Column("k2o_pct", sa.String(), nullable=True),
        sa.Column("p2o5_pct", sa.String(), nullable=True),
        sa.Column("loi_pct", sa.String(), nullable=True),
        sa.Column("f_pct", sa.String(), nullable=True),
        sa.Column("s_pct", sa.String(), nullable=True),
        sa.Column("so3_pct", sa.String(), nullable=True),
        sa.Column("so4_pct", sa.String(), nullable=True),
        sa.Column("c_pct", sa.String(), nullable=True),
        sa.Column("co2_pct", sa.String(), nullable=True),
        sa.Column("total_pct", sa.String(), nullable=True),
        sa.Column("feo_pct", sa.String(), nullable=True),
        sa.Column("fe2o3_pct", sa.String(), nullable=True),
        sa.Column("feo_star_pct", sa.String(), nullable=True),
        sa.Column("h2o_plus_pct", sa.String(), nullable=True),
        sa.Column("h2o_minus_pct", sa.String(), nullable=True),
        sa.Column("au_ppb", sa.String(), nullable=True),
        sa.Column("ag_ppm", sa.String(), nullable=True),
        sa.Column("as_ppm", sa.String(), nullable=True),
        sa.Column("b_ppm", sa.String(), nullable=True),
        sa.Column("ba_ppm", sa.String(), nullable=True),
        sa.Column("be_ppm", sa.String(), nullable=True),
        sa.Column("bi_ppm", sa.String(), nullable=True),
        sa.Column("br_ppm", sa.String(), nullable=True),
        sa.Column("cd_ppm", sa.String(), nullable=True),
        sa.Column("cl_ppm", sa.String(), nullable=True),
        sa.Column("co_ppm", sa.String(), nullable=True),
        sa.Column("cr_ppm", sa.String(), nullable=True),
        sa.Column("cs_ppm", sa.String(), nullable=True),
        sa.Column("cu_ppm", sa.String(), nullable=True),
        sa.Column("ga_ppm", sa.String(), nullable=True),
        sa.Column("ge_ppm", sa.String(), nullable=True),
        sa.Column("hf_ppm", sa.String(), nullable=True),
        sa.Column("hg_ppm", sa.String(), nullable=True),
        sa.Column("in_ppm", sa.String(), nullable=True),
        sa.Column("li_ppm", sa.String(), nullable=True),
        sa.Column("mo_ppm", sa.String(), nullable=True),
        sa.Column("nb_ppm", sa.String(), nullable=True),
        sa.Column("ni_ppm", sa.String(), nullable=True),
        sa.Column("pd_ppm", sa.String(), nullable=True),
        sa.Column("pb_ppm", sa.String(), nullable=True),
        sa.Column("pt_ppm", sa.String(), nullable=True),
        sa.Column("rb_ppm", sa.String(), nullable=True),
        sa.Column("re_ppm", sa.String(), nullable=True),
        sa.Column("sb_ppm", sa.String(), nullable=True),
        sa.Column("sc_ppm", sa.String(), nullable=True),
        sa.Column("se_ppm", sa.String(), nullable=True),
        sa.Column("sn_ppm", sa.String(), nullable=True),
        sa.Column("sr_ppm", sa.String(), nullable=True),
        sa.Column("ta_ppm", sa.String(), nullable=True),
        sa.Column("te_ppm", sa.String(), nullable=True),
        sa.Column("th_ppm", sa.String(), nullable=True),
        sa.Column("tl_ppm", sa.String(), nullable=True),
        sa.Column("u_ppm", sa.String(), nullable=True),
        sa.Column("v_ppm", sa.String(), nullable=True),
        sa.Column("w_ppm", sa.String(), nullable=True),
        sa.Column("y_ppm", sa.String(), nullable=True),
        sa.Column("zn_ppm", sa.String(), nullable=True),
        sa.Column("zr_ppm", sa.String(), nullable=True),
        sa.Column("la_ppm", sa.String(), nullable=True),
        sa.Column("ce_ppm", sa.String(), nullable=True),
        sa.Column("pr_ppm", sa.String(), nullable=True),
        sa.Column("nd_ppm", sa.String(), nullable=True),
        sa.Column("sm_ppm", sa.String(), nullable=True),
        sa.Column("eu_ppm", sa.String(), nullable=True),
        sa.Column("gd_ppm", sa.String(), nullable=True),
        sa.Column("tb_ppm", sa.String(), nullable=True),
        sa.Column("dy_ppm", sa.String(), nullable=True),
        sa.Column("ho_ppm", sa.String(), nullable=True),
        sa.Column("er_ppm", sa.String(), nullable=True),
        sa.Column("tm_ppm", sa.String(), nullable=True),
        sa.Column("yb_ppm", sa.String(), nullable=True),
        sa.Column("lu_ppm", sa.String(), nullable=True),
        sa.Column("tree_ppm", sa.String(), nullable=True),
        sa.Column("mn_pct", sa.String(), nullable=True),
        sa.Column("fe_pct", sa.String(), nullable=True),
        sa.Column("al_pct", sa.String(), nullable=True),
        sa.Column("ca_pct", sa.String(), nullable=True),
        sa.Column("na_pct", sa.String(), nullable=True),
        sa.Column("k_pct", sa.String(), nullable=True),
        sa.Column("mg_pct", sa.String(), nullable=True),
        sa.Column("p_pct", sa.String(), nullable=True),
        sa.Column("si_pct", sa.String(), nullable=True),
        sa.Column("ti_pct", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_sheet", "source_row", name="uq_cm_chemical_data_source_row"
        ),
    )
    op.create_index("ix_CM_ChemicalData_area", "CM_ChemicalData", ["area"])
    op.create_index("ix_CM_ChemicalData_sample", "CM_ChemicalData", ["sample"])
    op.create_index(
        "ix_CM_ChemicalData_source_sheet", "CM_ChemicalData", ["source_sheet"]
    )

    op.create_table(
        "CM_DetectionLimits",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("element", sa.String(), nullable=True),
        sa.Column("lower_reporting_limit", sa.String(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row", name="uq_cm_detection_limits_source_row"),
    )
    op.create_index("ix_CM_DetectionLimits_element", "CM_DetectionLimits", ["element"])

    op.create_table(
        "CM_References",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("citation", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row", name="uq_cm_references_source_row"),
    )

    op.create_table(
        "CM_MineralSystems",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("system_name", sa.String(), nullable=True),
        sa.Column("synopsis", sa.String(), nullable=True),
        sa.Column("deposit_types", sa.String(), nullable=True),
        sa.Column("principal_commodities", sa.String(), nullable=True),
        sa.Column("critical_minerals", sa.String(), nullable=True),
        sa.Column("references", sa.String(), nullable=True),
        sa.Column("phase_2", sa.String(), nullable=True),
        sa.Column("phase_3", sa.String(), nullable=True),
        sa.Column("phase_4", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row", name="uq_cm_mineral_systems_source_row"),
    )

    op.create_table(
        "CM_WorldComparisons",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("deposit", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("la", sa.String(), nullable=True),
        sa.Column("ce", sa.String(), nullable=True),
        sa.Column("pr", sa.String(), nullable=True),
        sa.Column("nd", sa.String(), nullable=True),
        sa.Column("sm", sa.String(), nullable=True),
        sa.Column("eu", sa.String(), nullable=True),
        sa.Column("gd", sa.String(), nullable=True),
        sa.Column("tb", sa.String(), nullable=True),
        sa.Column("dy", sa.String(), nullable=True),
        sa.Column("ho", sa.String(), nullable=True),
        sa.Column("er", sa.String(), nullable=True),
        sa.Column("tm", sa.String(), nullable=True),
        sa.Column("yb", sa.String(), nullable=True),
        sa.Column("lu", sa.String(), nullable=True),
        sa.Column("tree", sa.String(), nullable=True),
        sa.Column("sc", sa.String(), nullable=True),
        sa.Column("y", sa.String(), nullable=True),
        sa.Column("metric_tons", sa.String(), nullable=True),
        sa.Column("grade_pct", sa.String(), nullable=True),
        sa.Column("total_ree", sa.String(), nullable=True),
        sa.Column("cutoff_grade_pct", sa.String(), nullable=True),
        sa.Column("la2o3", sa.String(), nullable=True),
        sa.Column("ce2o3", sa.String(), nullable=True),
        sa.Column("pr6o11", sa.String(), nullable=True),
        sa.Column("nd2o3", sa.String(), nullable=True),
        sa.Column("sm2o3", sa.String(), nullable=True),
        sa.Column("eu2o3", sa.String(), nullable=True),
        sa.Column("gd2o3", sa.String(), nullable=True),
        sa.Column("tb4o7", sa.String(), nullable=True),
        sa.Column("dy2o3", sa.String(), nullable=True),
        sa.Column("ho2o3", sa.String(), nullable=True),
        sa.Column("er2o3", sa.String(), nullable=True),
        sa.Column("tm2o3", sa.String(), nullable=True),
        sa.Column("yb2o3", sa.String(), nullable=True),
        sa.Column("lu2o3", sa.String(), nullable=True),
        sa.Column("y2o3", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row", name="uq_cm_world_comparisons_source_row"),
    )

    op.create_table(
        "CM_WorldReferences",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("citation", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row", name="uq_cm_world_references_source_row"),
    )

    op.create_table(
        "CM_WorkbookMetadata",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("source_sheet", sa.String(), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("value", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_sheet", "source_row", name="uq_cm_workbook_metadata_source_row"
        ),
    )


def downgrade() -> None:
    op.drop_table("CM_WorkbookMetadata")
    op.drop_table("CM_WorldReferences")
    op.drop_table("CM_WorldComparisons")
    op.drop_table("CM_MineralSystems")
    op.drop_table("CM_References")
    op.drop_index("ix_CM_DetectionLimits_element", table_name="CM_DetectionLimits")
    op.drop_table("CM_DetectionLimits")
    op.drop_index("ix_CM_ChemicalData_area", table_name="CM_ChemicalData")
    op.drop_index("ix_CM_ChemicalData_sample", table_name="CM_ChemicalData")
    op.drop_index("ix_CM_ChemicalData_source_sheet", table_name="CM_ChemicalData")
    op.drop_table("CM_ChemicalData")
