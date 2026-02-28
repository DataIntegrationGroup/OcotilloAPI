"""add chemistry backfill columns to observation and sample

Revision ID: 545a5b77e5e8
Revises: d5e6f7a8b9c0
Create Date: 2026-02-27 11:30:45.380002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '545a5b77e5e8'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add chemistry backfill columns to observation and sample tables."""
    # Observation table: 4 new columns
    op.add_column('observation', sa.Column(
        'nma_pk_chemistryresults', sa.String(), nullable=True,
        comment='NM_Aquifer GlobalID for chemistry results — transfer audit and idempotent upsert key',
    ))
    op.add_column('observation', sa.Column(
        'detect_flag', sa.Boolean(), nullable=True,
        comment="True=detected, False=below detection limit (legacy Symbol '<'), None=no qualifier",
    ))
    op.add_column('observation', sa.Column(
        'uncertainty', sa.Float(), nullable=True,
        comment='Measurement uncertainty for the observation value',
    ))
    op.add_column('observation', sa.Column(
        'analysis_agency', sa.String(), nullable=True,
        comment='Agency or lab that performed the analysis',
    ))
    op.create_unique_constraint(
        'uq_observation_nma_pk_chemistryresults',
        'observation', ['nma_pk_chemistryresults'],
    )

    # Observation version table (sqlalchemy-continuum)
    op.add_column('observation_version', sa.Column(
        'nma_pk_chemistryresults', sa.String(), autoincrement=False, nullable=True,
        comment='NM_Aquifer GlobalID for chemistry results — transfer audit and idempotent upsert key',
    ))
    op.add_column('observation_version', sa.Column(
        'detect_flag', sa.Boolean(), autoincrement=False, nullable=True,
        comment="True=detected, False=below detection limit (legacy Symbol '<'), None=no qualifier",
    ))
    op.add_column('observation_version', sa.Column(
        'uncertainty', sa.Float(), autoincrement=False, nullable=True,
        comment='Measurement uncertainty for the observation value',
    ))
    op.add_column('observation_version', sa.Column(
        'analysis_agency', sa.String(), autoincrement=False, nullable=True,
        comment='Agency or lab that performed the analysis',
    ))

    # Sample table: 3 new columns
    op.add_column('sample', sa.Column(
        'nma_pk_chemistrysample', sa.String(), nullable=True,
        comment='NM_Aquifer SamplePtID for chemistry samples — transfer audit key',
    ))
    op.add_column('sample', sa.Column(
        'volume', sa.Float(), nullable=True,
        comment='Volume of the sample collected',
    ))
    op.add_column('sample', sa.Column(
        'volume_unit', sa.String(), nullable=True,
        comment='Unit for the sample volume (e.g. mL, L)',
    ))
    op.create_unique_constraint(
        'uq_sample_nma_pk_chemistrysample',
        'sample', ['nma_pk_chemistrysample'],
    )

    # Drop stale thing_id column from NMA_Radionuclides (model no longer defines it;
    # relationships go through NMA_Chemistry_SampleInfo.thing_id instead).
    # Guard against environments where the column was already removed.
    conn = op.get_bind()
    has_thing_id = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'NMA_Radionuclides' AND column_name = 'thing_id'"
    )).scalar()
    if has_thing_id:
        # FK name may differ across environments; look it up dynamically.
        fks = sa.inspect(conn).get_foreign_keys('NMA_Radionuclides')
        for fk in fks:
            if 'thing_id' in fk['constrained_columns'] and fk.get('name'):
                op.drop_constraint(fk['name'], 'NMA_Radionuclides', type_='foreignkey')
        op.drop_column('NMA_Radionuclides', 'thing_id')


def downgrade() -> None:
    """Remove chemistry backfill columns."""
    # Restore NMA_Radionuclides.thing_id (add nullable, backfill, then enforce)
    op.add_column('NMA_Radionuclides', sa.Column(
        'thing_id', sa.Integer(), nullable=True,
    ))
    op.execute(
        'UPDATE "NMA_Radionuclides" r '
        'SET thing_id = csi.thing_id '
        'FROM "NMA_Chemistry_SampleInfo" csi '
        'WHERE r.chemistry_sample_info_id = csi.id'
    )
    op.alter_column('NMA_Radionuclides', 'thing_id', nullable=False)
    op.create_foreign_key(
        'NMA_Radionuclides_thing_id_fkey', 'NMA_Radionuclides', 'thing',
        ['thing_id'], ['id'], ondelete='CASCADE',
    )

    op.drop_constraint('uq_sample_nma_pk_chemistrysample', 'sample', type_='unique')
    op.drop_column('sample', 'volume_unit')
    op.drop_column('sample', 'volume')
    op.drop_column('sample', 'nma_pk_chemistrysample')

    op.drop_column('observation_version', 'analysis_agency')
    op.drop_column('observation_version', 'uncertainty')
    op.drop_column('observation_version', 'detect_flag')
    op.drop_column('observation_version', 'nma_pk_chemistryresults')

    op.drop_constraint('uq_observation_nma_pk_chemistryresults', 'observation', type_='unique')
    op.drop_column('observation', 'analysis_agency')
    op.drop_column('observation', 'uncertainty')
    op.drop_column('observation', 'detect_flag')
    op.drop_column('observation', 'nma_pk_chemistryresults')
