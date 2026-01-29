"""Change NMA_Chemistry_SampleInfo FK from thing_id to location_id.

Revision ID: h1i2j3k4l5m6
Revises: 3cb924ca51fd
Create Date: 2026-01-29 12:00:00.000000

This migration changes NMA_Chemistry_SampleInfo to FK to Location instead of Thing.
- 99.95% of chemistry records have valid LocationId -> Location match
- Only ~2 truly orphan records (will be filtered during transfer)
- Simpler and more complete than Thing matching
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "3cb924ca51fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change FK from thing_id to location_id on NMA_Chemistry_SampleInfo.

    Steps:
    1. Add location_id column (nullable initially)
    2. Populate location_id by joining nma_LocationId -> Location.nma_pk_location
    3. Handle any NULL location_ids (delete orphan records)
    4. Make location_id NOT NULL
    5. Drop thing_id FK constraint and column
    6. Add location_id FK constraint
    """
    bind = op.get_bind()

    # Step 1: Add location_id column (nullable initially)
    op.add_column(
        "NMA_Chemistry_SampleInfo",
        sa.Column("location_id", sa.Integer(), nullable=True),
    )

    # Step 2: Populate location_id from nma_LocationId -> Location.nma_pk_location
    # Location.nma_pk_location is stored as String(36), so cast UUID to text for comparison
    bind.execute(
        sa.text(
            """
            UPDATE "NMA_Chemistry_SampleInfo" csi
            SET location_id = l.id
            FROM location l
            WHERE CAST(csi."nma_LocationId" AS TEXT) = l.nma_pk_location
            """
        )
    )

    # Step 3: Delete orphan records where location_id is still NULL
    # These are records with LocationIds that don't exist in the Location table
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM "NMA_Chemistry_SampleInfo" WHERE location_id IS NULL
            """
        )
    )
    orphan_count = result.scalar()
    if orphan_count and orphan_count > 0:
        print(f"Deleting {orphan_count} orphan NMA_Chemistry_SampleInfo records (no matching Location)")
        bind.execute(
            sa.text(
                """
                DELETE FROM "NMA_Chemistry_SampleInfo" WHERE location_id IS NULL
                """
            )
        )

    # Step 4: Make location_id NOT NULL
    op.alter_column(
        "NMA_Chemistry_SampleInfo",
        "location_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Step 5: Drop thing_id FK constraint and column
    # First, drop the FK constraint
    op.drop_constraint(
        "NMA_Chemistry_SampleInfo_thing_id_fkey",
        "NMA_Chemistry_SampleInfo",
        type_="foreignkey",
    )
    # Then drop the column
    op.drop_column("NMA_Chemistry_SampleInfo", "thing_id")

    # Step 6: Add location_id FK constraint
    op.create_foreign_key(
        "NMA_Chemistry_SampleInfo_location_id_fkey",
        "NMA_Chemistry_SampleInfo",
        "location",
        ["location_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Add index for location_id for better query performance
    op.create_index(
        "ix_nma_chemistry_sampleinfo_location_id",
        "NMA_Chemistry_SampleInfo",
        ["location_id"],
    )


def downgrade() -> None:
    """Revert FK from location_id back to thing_id.

    Note: This downgrade assumes Things exist with matching names.
    Data loss may occur if Things were deleted.
    """
    bind = op.get_bind()

    # Drop the index on location_id
    op.drop_index(
        "ix_nma_chemistry_sampleinfo_location_id",
        table_name="NMA_Chemistry_SampleInfo",
    )

    # Drop location_id FK constraint
    op.drop_constraint(
        "NMA_Chemistry_SampleInfo_location_id_fkey",
        "NMA_Chemistry_SampleInfo",
        type_="foreignkey",
    )

    # Add thing_id column (nullable initially)
    op.add_column(
        "NMA_Chemistry_SampleInfo",
        sa.Column("thing_id", sa.Integer(), nullable=True),
    )

    # Populate thing_id by joining nma_SamplePointID -> Thing.name
    # This is the reverse of what we did - mapping chemistry records back to Things
    bind.execute(
        sa.text(
            """
            UPDATE "NMA_Chemistry_SampleInfo" csi
            SET thing_id = t.id
            FROM thing t
            WHERE UPPER(TRIM(csi."nma_SamplePointID")) = UPPER(TRIM(t.name))
            """
        )
    )

    # For records that couldn't find a Thing match, try to match via Location -> Thing association
    bind.execute(
        sa.text(
            """
            UPDATE "NMA_Chemistry_SampleInfo" csi
            SET thing_id = lta.thing_id
            FROM location_thing_association lta
            WHERE csi.location_id = lta.location_id
              AND csi.thing_id IS NULL
            """
        )
    )

    # Delete any remaining orphans (cannot be linked to a Thing)
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM "NMA_Chemistry_SampleInfo" WHERE thing_id IS NULL
            """
        )
    )
    orphan_count = result.scalar()
    if orphan_count and orphan_count > 0:
        print(f"Deleting {orphan_count} orphan NMA_Chemistry_SampleInfo records (no matching Thing)")
        bind.execute(
            sa.text(
                """
                DELETE FROM "NMA_Chemistry_SampleInfo" WHERE thing_id IS NULL
                """
            )
        )

    # Make thing_id NOT NULL
    op.alter_column(
        "NMA_Chemistry_SampleInfo",
        "thing_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Drop location_id column
    op.drop_column("NMA_Chemistry_SampleInfo", "location_id")

    # Add thing_id FK constraint
    op.create_foreign_key(
        "NMA_Chemistry_SampleInfo_thing_id_fkey",
        "NMA_Chemistry_SampleInfo",
        "thing",
        ["thing_id"],
        ["id"],
        ondelete="CASCADE",
    )
