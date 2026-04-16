# flake8: noqa: E501
"""create aem tables

Revision ID: a8c9d0e1f2b3
Revises: t6u7v8w9x0y1
Create Date: 2026-04-16 15:50:00.000000
"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision = "a8c9d0e1f2b3"
down_revision = "t6u7v8w9x0y1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aem_soundings",
        sa.Column("sounding_id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("survey_id", sa.Text(), nullable=False),
        sa.Column(
            "processing_stage",
            sa.Text(),
            nullable=False,
            comment="'preliminary_inversion' or 'final_inversion'",
        ),
        sa.Column(
            "inversion_code",
            sa.Text(),
            nullable=True,
            comment="'seogi_python' | 'aarhus_sci' | 'aarhus_lci'",
        ),
        sa.Column("contractor", sa.Text(), nullable=True),
        sa.Column(
            "source_file",
            sa.Text(),
            nullable=True,
            comment="GCS path of the original source file",
        ),
        sa.Column(
            "source_epsg",
            sa.Integer(),
            nullable=True,
            comment="Original CRS before reprojection (e.g. 32613 for Seogi)",
        ),
        sa.Column("line_id", sa.Text(), nullable=False),
        sa.Column(
            "record_id",
            sa.Text(),
            nullable=True,
            comment=(
                "TEXT not INTEGER — Seogi record resets to 1 per flight subfolder. "
                "Prefixed with flight ID (e.g. F02_1) to be unique across survey."
            ),
        ),
        sa.Column("layer_no", sa.SmallInteger(), nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=26913),
            nullable=False,
            comment="PostGIS point in NAD83 UTM Zone 13N",
        ),
        sa.Column("easting_m", sa.Float(), nullable=False),
        sa.Column("northing_m", sa.Float(), nullable=False),
        sa.Column("longitude_dd", sa.Float(), nullable=True),
        sa.Column("latitude_dd", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("sensor_alt_m", sa.Float(), nullable=True),
        sa.Column("terrain_clear_m", sa.Float(), nullable=True),
        sa.Column("depth_top_m", sa.Float(), nullable=False),
        sa.Column("depth_bot_m", sa.Float(), nullable=False),
        sa.Column(
            "thickness_m",
            sa.Float(),
            nullable=True,
            comment="NULL for Seogi outputs",
        ),
        sa.Column("resistivity_ohmm", sa.Float(), nullable=False),
        sa.Column(
            "resistivity_std",
            sa.Float(),
            nullable=True,
            comment="NULL for Seogi — pipeline doesn't produce uncertainty",
        ),
        sa.Column(
            "conductivity_sm",
            sa.Float(),
            nullable=True,
            comment="NULL for Seogi",
        ),
        sa.Column(
            "doi_conservative_m",
            sa.Float(),
            nullable=True,
            comment="NULL for Seogi",
        ),
        sa.Column(
            "doi_standard_m",
            sa.Float(),
            nullable=True,
            comment="NULL for Seogi",
        ),
        sa.Column("resdata", sa.Float(), nullable=True),
        sa.Column("restotal", sa.Float(), nullable=True),
        sa.Column("plni", sa.Float(), nullable=True),
        sa.Column("date_acquired", sa.Date(), nullable=True),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("sounding_id"),
    )
    op.create_index(
        "idx_soundings_final",
        "aem_soundings",
        ["survey_id", "line_id"],
        unique=False,
        postgresql_where=sa.text("processing_stage = 'final_inversion'"),
    )
    op.create_index(
        "idx_soundings_depth",
        "aem_soundings",
        ["depth_top_m", "depth_bot_m"],
        unique=False,
    )
    op.create_index(
        "idx_soundings_geom",
        "aem_soundings",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_soundings_line",
        "aem_soundings",
        ["survey_id", "line_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_aem_soundings_survey_id"),
        "aem_soundings",
        ["survey_id"],
        unique=False,
    )
    op.create_index(
        "idx_soundings_survey_stage",
        "aem_soundings",
        ["survey_id", "processing_stage"],
        unique=False,
    )

    op.create_table(
        "aem_sounding_metadata",
        sa.Column("survey_id", sa.Text(), nullable=False),
        sa.Column("line_id", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column("processing_stage", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=26913),
            nullable=False,
        ),
        sa.Column("easting_m", sa.Float(), nullable=False),
        sa.Column("northing_m", sa.Float(), nullable=False),
        sa.Column("flight_id", sa.Text(), nullable=True),
        sa.Column("date_acquired", sa.Date(), nullable=True),
        sa.Column("num_layers", sa.SmallInteger(), nullable=True),
        sa.Column("max_depth_m", sa.Float(), nullable=True),
        sa.Column("has_uncertainty", sa.Boolean(), nullable=False),
        sa.Column("has_doi", sa.Boolean(), nullable=False),
        sa.Column("inversion_code", sa.Text(), nullable=True),
        sa.Column("source_epsg", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint(
            "survey_id", "line_id", "record_id", "processing_stage"
        ),
    )
    op.create_index(
        "idx_metadata_geom",
        "aem_sounding_metadata",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_metadata_survey",
        "aem_sounding_metadata",
        ["survey_id", "processing_stage"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_metadata_survey", table_name="aem_sounding_metadata")
    op.drop_index(
        "idx_metadata_geom",
        table_name="aem_sounding_metadata",
        postgresql_using="gist",
    )
    op.drop_table("aem_sounding_metadata")
    op.drop_index("idx_soundings_survey_stage", table_name="aem_soundings")
    op.drop_index(op.f("ix_aem_soundings_survey_id"), table_name="aem_soundings")
    op.drop_index("idx_soundings_line", table_name="aem_soundings")
    op.drop_index(
        "idx_soundings_geom", table_name="aem_soundings", postgresql_using="gist"
    )
    op.drop_index("idx_soundings_depth", table_name="aem_soundings")
    op.drop_index("idx_soundings_final", table_name="aem_soundings")
    op.drop_table("aem_soundings")
