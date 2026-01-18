"""Ensure NGWMN unique constraints for upserts

Revision ID: 5f4e2b0a6b8b
Revises: 4b7aa74b15ad
Create Date: 2026-02-10 01:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f4e2b0a6b8b"
down_revision: Union[str, Sequence[str], None] = "4b7aa74b15ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraints needed for ON CONFLICT upserts (idempotent)."""
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_waterlevels_point_date'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_WaterLevels"
                ADD CONSTRAINT uq_nma_view_ngwmn_waterlevels_point_date UNIQUE ("PointID", "DateMeasured");
            END IF;
        END;
        $$;
        """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_wellconstruction_point_casing_screen'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_WellConstruction"
                ADD CONSTRAINT uq_nma_view_ngwmn_wellconstruction_point_casing_screen
                UNIQUE ("PointID", "CasingTop", "ScreenTop");
            END IF;
        END;
        $$;
        """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_lithology_objectid'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_Lithology"
                ADD CONSTRAINT uq_nma_view_ngwmn_lithology_objectid UNIQUE ("OBJECTID");
            END IF;
        END;
        $$;
        """)


def downgrade() -> None:
    """Drop the NGWMN unique constraints if they exist."""
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_waterlevels_point_date'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_WaterLevels"
                DROP CONSTRAINT uq_nma_view_ngwmn_waterlevels_point_date;
            END IF;
        END;
        $$;
        """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_wellconstruction_point_casing_screen'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_WellConstruction"
                DROP CONSTRAINT uq_nma_view_ngwmn_wellconstruction_point_casing_screen;
            END IF;
        END;
        $$;
        """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_nma_view_ngwmn_lithology_objectid'
            ) THEN
                ALTER TABLE "NMA_view_NGWMN_Lithology"
                DROP CONSTRAINT uq_nma_view_ngwmn_lithology_objectid;
            END IF;
        END;
        $$;
        """)
