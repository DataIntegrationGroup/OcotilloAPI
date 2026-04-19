# flake8: noqa: E501
"""create stac oseo schema

Revision ID: b9d0e1f2a3b4
Revises: a8c9d0e1f2b3
Create Date: 2026-04-19 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "a8c9d0e1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "stac"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text('CREATE SCHEMA IF NOT EXISTS "stac"'))

    op.create_table(
        "collection",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("primary", sa.Boolean(), nullable=True),
        sa.Column(
            "footprint",
            Geometry(geometry_type="POLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("timeStart", sa.DateTime(), nullable=True),
        sa.Column("timeEnd", sa.DateTime(), nullable=True),
        sa.Column("productCqlFilter", sa.String(), nullable=True),
        sa.Column("masked", sa.Boolean(), nullable=True),
        sa.Column("eoIdentifier", sa.String(), nullable=True, unique=True),
        sa.Column("eoProductType", sa.String(), nullable=True),
        sa.Column("eoPlatform", sa.String(), nullable=True),
        sa.Column("eoPlatformSerialIdentifier", sa.String(), nullable=True),
        sa.Column("eoInstrument", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("eoSensorType", sa.String(), nullable=True),
        sa.Column("eoCompositeType", sa.String(), nullable=True),
        sa.Column("eoProcessingLevel", sa.String(), nullable=True),
        sa.Column("eoOrbitType", sa.String(), nullable=True),
        sa.Column("eoSpectralRange", sa.String(), nullable=True),
        sa.Column("eoWavelength", sa.Integer(), nullable=True),
        sa.Column("eoSecurityConstraints", sa.Boolean(), nullable=True),
        sa.Column("eoDissemination", sa.String(), nullable=True),
        sa.Column("eoAcquisitionStation", sa.String(), nullable=True),
        sa.Column("license", sa.String(), nullable=True),
        sa.Column("queryables", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("workspaces", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assets", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_collection_footprint",
        "collection",
        ["footprint"],
        unique=False,
        schema=SCHEMA,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_stac_collection_timestart",
        "collection",
        ["timeStart"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_collection_timeend",
        "collection",
        ["timeEnd"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_collection_eoidentifier",
        "collection",
        ["eoIdentifier"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "collection_layer",
        sa.Column("lid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("cid", sa.Integer(), nullable=True),
        sa.Column("workspace", sa.String(), nullable=True),
        sa.Column("layer", sa.String(), nullable=True),
        sa.Column("separateBands", sa.Boolean(), nullable=True),
        sa.Column("bands", sa.String(), nullable=True),
        sa.Column("browseBands", sa.String(), nullable=True),
        sa.Column("heterogeneousCRS", sa.Boolean(), nullable=True),
        sa.Column("mosaicCRS", sa.String(), nullable=True),
        sa.Column("defaultLayer", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cid"], [f"{SCHEMA}.collection.id"], ondelete="CASCADE"
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "footprint",
            Geometry(geometry_type="POLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("timeStart", sa.DateTime(), nullable=True),
        sa.Column("timeEnd", sa.DateTime(), nullable=True),
        sa.Column("originalPackageLocation", sa.String(), nullable=True),
        sa.Column("originalPackageType", sa.String(), nullable=True),
        sa.Column("thumbnailURL", sa.String(), nullable=True),
        sa.Column("quicklookURL", sa.String(), nullable=True),
        sa.Column("crs", sa.String(), nullable=True),
        sa.Column("eoIdentifier", sa.String(), nullable=True, unique=True),
        sa.Column("eoParentIdentifier", sa.String(), nullable=True),
        sa.Column("eoProductionStatus", sa.String(), nullable=True),
        sa.Column("eoAcquisitionType", sa.String(), nullable=True),
        sa.Column("eoOrbitNumber", sa.Integer(), nullable=True),
        sa.Column("eoOrbitDirection", sa.String(), nullable=True),
        sa.Column("eoTrack", sa.Integer(), nullable=True),
        sa.Column("eoFrame", sa.Integer(), nullable=True),
        sa.Column("eoSwathIdentifier", sa.Text(), nullable=True),
        sa.Column("eoProductPlatform", sa.String(), nullable=True),
        sa.Column("optCloudCover", sa.Integer(), nullable=True),
        sa.Column("optSnowCover", sa.Integer(), nullable=True),
        sa.Column("eoProductQualityStatus", sa.String(), nullable=True),
        sa.Column("eoProductQualityDegradationStatus", sa.String(), nullable=True),
        sa.Column("eoProcessorName", sa.String(), nullable=True),
        sa.Column("eoProcessingCenter", sa.String(), nullable=True),
        sa.Column("eoCreationDate", sa.DateTime(), nullable=True),
        sa.Column("eoModificationDate", sa.DateTime(), nullable=True),
        sa.Column("eoProcessingDate", sa.DateTime(), nullable=True),
        sa.Column("eoSensorMode", sa.String(), nullable=True),
        sa.Column("eoArchivingCenter", sa.String(), nullable=True),
        sa.Column("eoProcessingMode", sa.String(), nullable=True),
        sa.Column("eoAvailabilityTime", sa.DateTime(), nullable=True),
        sa.Column("eoAcquisitionStation", sa.String(), nullable=True),
        sa.Column("eoAcquisitionSubtype", sa.String(), nullable=True),
        sa.Column("eoStartTimeFromAscendingNode", sa.Integer(), nullable=True),
        sa.Column("eoCompletionTimeFromAscendingNode", sa.Integer(), nullable=True),
        sa.Column("eoIlluminationAzimuthAngle", sa.Float(), nullable=True),
        sa.Column("eoIlluminationZenithAngle", sa.Float(), nullable=True),
        sa.Column("eoIlluminationElevationAngle", sa.Float(), nullable=True),
        sa.Column("sarPolarisationMode", sa.String(), nullable=True),
        sa.Column("sarPolarisationChannels", sa.String(), nullable=True),
        sa.Column("sarAntennaLookDirection", sa.String(), nullable=True),
        sa.Column("sarMinimumIncidenceAngle", sa.Float(), nullable=True),
        sa.Column("sarMaximumIncidenceAngle", sa.Float(), nullable=True),
        sa.Column("sarDopplerFrequency", sa.Float(), nullable=True),
        sa.Column("sarIncidenceAngleVariation", sa.Float(), nullable=True),
        sa.Column("eoResolution", sa.Float(), nullable=True),
        sa.Column("atmVerticalRange", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column(
            "atmVerticalResolution",
            postgresql.ARRAY(sa.Float()),
            nullable=True,
        ),
        sa.Column("atmSpecies", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("atmSpeciesError", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("atmUnit", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("atmAlgorithmName", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("atmAlgorithmVersion", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assets", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("assetsb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.ForeignKeyConstraint(
            ["eoParentIdentifier"],
            [f"{SCHEMA}.collection.eoIdentifier"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "\"eoAcquisitionType\" IN ('NOMINAL', 'CALIBRATION', 'OTHER')",
            name="ck_stac_product_eoacquisitiontype",
        ),
        sa.CheckConstraint(
            "\"eoOrbitDirection\" IN ('ASCENDING', 'DESCENDING')",
            name="ck_stac_product_eoorbitdirection",
        ),
        sa.CheckConstraint(
            '"optCloudCover" BETWEEN 0 AND 100',
            name="ck_stac_product_optcloudcover",
        ),
        sa.CheckConstraint(
            '"optSnowCover" BETWEEN 0 AND 100',
            name="ck_stac_product_optsnowcover",
        ),
        sa.CheckConstraint(
            "\"eoProductQualityStatus\" IN ('NOMINAL', 'DEGRADED')",
            name="ck_stac_product_eoproductqualitystatus",
        ),
        sa.CheckConstraint(
            "\"sarPolarisationMode\" IN ('S', 'D', 'T', 'Q', 'UNDEFINED')",
            name="ck_stac_product_sarpolarisationmode",
        ),
        sa.CheckConstraint(
            "\"sarPolarisationChannels\" IN ('horizontal', 'vertical')",
            name="ck_stac_product_sarpolarisationchannels",
        ),
        sa.CheckConstraint(
            "\"sarAntennaLookDirection\" IN ('LEFT', 'RIGHT')",
            name="ck_stac_product_sarantennalookdirection",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_product_footprint",
        "product",
        ["footprint"],
        unique=False,
        schema=SCHEMA,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_stac_product_parent_time",
        "product",
        ["eoParentIdentifier", "timeEnd", "timeStart"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_product_eoidentifier",
        "product",
        ["eoIdentifier"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "queryable_idx_tracker",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("collection", sa.String(), nullable=True),
        sa.Column("queryable", sa.String(), nullable=True),
        sa.Column("expression", sa.String(), nullable=True),
        sa.Column("index_name", sa.String(), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_q_tracker_index_name",
        "queryable_idx_tracker",
        ["index_name"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "product_thumb",
        sa.Column("tid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("thumb", sa.LargeBinary(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tid"],
            [f"{SCHEMA}.product.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "collection_ogclink",
        sa.Column("lid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=True),
        sa.Column("offering", sa.String(), nullable=True),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("href", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            [f"{SCHEMA}.collection.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "product_ogclink",
        sa.Column("lid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("offering", sa.String(), nullable=True),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("href", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            [f"{SCHEMA}.product.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "granule",
        sa.Column("gid", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("band", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column(
            "the_geom",
            Geometry(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            [f"{SCHEMA}.product.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_stac_granule_the_geom",
        "granule",
        ["the_geom"],
        unique=False,
        schema=SCHEMA,
        postgresql_using="gist",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_stac_granule_the_geom", table_name="granule", schema=SCHEMA)
    op.drop_table("granule", schema=SCHEMA)
    op.drop_table("product_ogclink", schema=SCHEMA)
    op.drop_table("collection_ogclink", schema=SCHEMA)
    op.drop_table("product_thumb", schema=SCHEMA)
    op.drop_index(
        "idx_stac_q_tracker_index_name",
        table_name="queryable_idx_tracker",
        schema=SCHEMA,
    )
    op.drop_table("queryable_idx_tracker", schema=SCHEMA)
    op.drop_index("idx_stac_product_eoidentifier", table_name="product", schema=SCHEMA)
    op.drop_index("idx_stac_product_parent_time", table_name="product", schema=SCHEMA)
    op.drop_index("idx_stac_product_footprint", table_name="product", schema=SCHEMA)
    op.drop_table("product", schema=SCHEMA)
    op.drop_table("collection_layer", schema=SCHEMA)
    op.drop_index(
        "idx_stac_collection_eoidentifier",
        table_name="collection",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_stac_collection_timeend",
        table_name="collection",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_stac_collection_timestart",
        table_name="collection",
        schema=SCHEMA,
    )
    op.drop_index(
        "idx_stac_collection_footprint",
        table_name="collection",
        schema=SCHEMA,
    )
    op.drop_table("collection", schema=SCHEMA)
    op.execute(sa.text('DROP SCHEMA IF EXISTS "stac"'))
