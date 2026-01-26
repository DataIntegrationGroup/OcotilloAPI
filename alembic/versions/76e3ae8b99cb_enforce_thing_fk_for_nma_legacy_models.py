"""enforce_thing_fk_for_nma_legacy_models

Revision ID: 76e3ae8b99cb
Revises: c1d2e3f4a5b6
Create Date: 2026-01-26 11:56:28.744603

Issue: #363
Feature: features/admin/well_data_relationships.feature

This migration enforces foreign key relationships between Thing and NMA legacy models:
1. Adds nma_pk_location column to Thing for storing legacy NM_Aquifer LocationID
2. Makes thing_id NOT NULL on NMA_AssociatedData (was nullable)
3. Makes thing_id NOT NULL on NMA_Soil_Rock_Results (was nullable)

Note: Before running this migration, ensure no orphan records exist in the affected tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76e3ae8b99cb'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to enforce Thing FK relationships."""
    # 1. Add nma_pk_location column to thing table
    op.add_column(
        'thing',
        sa.Column(
            'nma_pk_location',
            sa.String(),
            nullable=True,
            comment='To audit the original NM_Aquifer LocationID if it was transferred over'
        )
    )

    # 2. Make thing_id NOT NULL on NMA_AssociatedData
    # First, delete any orphan records (records without a thing_id)
    op.execute(
        'DELETE FROM "NMA_AssociatedData" WHERE thing_id IS NULL'
    )
    op.alter_column(
        'NMA_AssociatedData',
        'thing_id',
        existing_type=sa.Integer(),
        nullable=False
    )

    # 3. Make thing_id NOT NULL on NMA_Soil_Rock_Results
    # First, delete any orphan records (records without a thing_id)
    op.execute(
        'DELETE FROM "NMA_Soil_Rock_Results" WHERE thing_id IS NULL'
    )
    op.alter_column(
        'NMA_Soil_Rock_Results',
        'thing_id',
        existing_type=sa.Integer(),
        nullable=False
    )


def downgrade() -> None:
    """Downgrade schema to allow nullable thing_id."""
    # 1. Remove nma_pk_location column from thing table
    op.drop_column('thing', 'nma_pk_location')

    # 2. Make thing_id nullable on NMA_AssociatedData
    op.alter_column(
        'NMA_AssociatedData',
        'thing_id',
        existing_type=sa.Integer(),
        nullable=True
    )

    # 3. Make thing_id nullable on NMA_Soil_Rock_Results
    op.alter_column(
        'NMA_Soil_Rock_Results',
        'thing_id',
        existing_type=sa.Integer(),
        nullable=True
    )
