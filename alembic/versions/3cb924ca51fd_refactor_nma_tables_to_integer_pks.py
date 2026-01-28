"""refactor_nma_tables_to_integer_pks

Revision ID: 3cb924ca51fd
Revises: 76e3ae8b99cb
Create Date: 2026-01-28 01:37:56.509497

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
import sqlalchemy_utils
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3cb924ca51fd'
down_revision: Union[str, Sequence[str], None] = '76e3ae8b99cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Refactor NMA legacy tables from UUID to Integer primary keys:
    - Add id (Integer PK with IDENTITY) to 8 NMA tables
    - Rename UUID columns with nma_ prefix for audit
    - Convert FK references from UUID to Integer
    - Make chemistry_sample_info_id NOT NULL for chemistry child tables
    """
    # ==========================================================================
    # PHASE 1: Drop ALL foreign keys that reference NMA_Chemistry_SampleInfo.SamplePtID
    # This must happen BEFORE we can modify NMA_Chemistry_SampleInfo
    # ==========================================================================
    op.drop_constraint(op.f('NMA_MinorTraceChemistry_chemistry_sample_info_id_fkey'), 'NMA_MinorTraceChemistry', type_='foreignkey')
    op.drop_constraint(op.f('NMA_Radionuclides_SamplePtID_fkey'), 'NMA_Radionuclides', type_='foreignkey')
    op.drop_constraint(op.f('NMA_MajorChemistry_SamplePtID_fkey'), 'NMA_MajorChemistry', type_='foreignkey')
    op.drop_constraint(op.f('NMA_FieldParameters_SamplePtID_fkey'), 'NMA_FieldParameters', type_='foreignkey')

    # ==========================================================================
    # PHASE 2: Modify NMA_Chemistry_SampleInfo (parent table)
    # ==========================================================================
    # Add new columns first
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('nma_SamplePtID', sa.UUID(), nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('nma_WCLab_ID', sa.String(length=18), nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('nma_SamplePointID', sa.String(length=10), nullable=False))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('nma_LocationId', sa.UUID(), nullable=True))

    # Drop old PK and create new PK on id
    op.drop_constraint('NMA_Chemistry_SampleInfo_pkey', 'NMA_Chemistry_SampleInfo', type_='primary')
    op.create_primary_key('NMA_Chemistry_SampleInfo_pkey', 'NMA_Chemistry_SampleInfo', ['id'])

    op.drop_constraint(op.f('NMA_Chemistry_SampleInfo_OBJECTID_key'), 'NMA_Chemistry_SampleInfo', type_='unique')
    op.create_unique_constraint(None, 'NMA_Chemistry_SampleInfo', ['nma_SamplePtID'])
    op.create_unique_constraint(None, 'NMA_Chemistry_SampleInfo', ['nma_OBJECTID'])
    op.drop_column('NMA_Chemistry_SampleInfo', 'SamplePointID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'SamplePtID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'WCLab_ID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'OBJECTID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'LocationId')

    # ==========================================================================
    # PHASE 3: Modify child tables and create new FKs pointing to NMA_Chemistry_SampleInfo.id
    # ==========================================================================

    # --- NMA_FieldParameters ---
    op.add_column('NMA_FieldParameters', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_FieldParameters', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_FieldParameters', sa.Column('chemistry_sample_info_id', sa.Integer(), nullable=False))
    op.add_column('NMA_FieldParameters', sa.Column('nma_SamplePtID', sa.UUID(), nullable=True))
    op.add_column('NMA_FieldParameters', sa.Column('nma_SamplePointID', sa.String(length=10), nullable=True))
    op.add_column('NMA_FieldParameters', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.add_column('NMA_FieldParameters', sa.Column('nma_WCLab_ID', sa.String(length=25), nullable=True))
    op.drop_index(op.f('FieldParameters$GlobalID'), table_name='NMA_FieldParameters')
    op.drop_index(op.f('FieldParameters$OBJECTID'), table_name='NMA_FieldParameters')
    op.drop_index(op.f('FieldParameters$SamplePointID'), table_name='NMA_FieldParameters')
    op.drop_index(op.f('FieldParameters$SamplePtID'), table_name='NMA_FieldParameters')
    op.drop_index(op.f('FieldParameters$WCLab_ID'), table_name='NMA_FieldParameters')
    op.drop_index(op.f('FieldParameters$ChemistrySampleInfoFieldParameters'), table_name='NMA_FieldParameters')
    op.create_index('FieldParameters$ChemistrySampleInfoFieldParameters', 'NMA_FieldParameters', ['chemistry_sample_info_id'], unique=False)
    op.create_index('FieldParameters$nma_GlobalID', 'NMA_FieldParameters', ['nma_GlobalID'], unique=True)
    op.create_index('FieldParameters$nma_OBJECTID', 'NMA_FieldParameters', ['nma_OBJECTID'], unique=True)
    op.create_index('FieldParameters$nma_SamplePointID', 'NMA_FieldParameters', ['nma_SamplePointID'], unique=False)
    op.create_index('FieldParameters$nma_WCLab_ID', 'NMA_FieldParameters', ['nma_WCLab_ID'], unique=False)
    op.create_unique_constraint(None, 'NMA_FieldParameters', ['nma_GlobalID'])
    op.create_foreign_key(None, 'NMA_FieldParameters', 'NMA_Chemistry_SampleInfo', ['chemistry_sample_info_id'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_column('NMA_FieldParameters', 'SamplePointID')
    op.drop_column('NMA_FieldParameters', 'SamplePtID')
    op.drop_column('NMA_FieldParameters', 'WCLab_ID')
    op.drop_column('NMA_FieldParameters', 'OBJECTID')
    op.drop_column('NMA_FieldParameters', 'GlobalID')

    # --- NMA_AssociatedData ---
    op.add_column('NMA_AssociatedData', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_AssociatedData', sa.Column('nma_AssocID', sa.UUID(), nullable=True))
    op.add_column('NMA_AssociatedData', sa.Column('nma_LocationId', sa.UUID(), nullable=True))
    op.add_column('NMA_AssociatedData', sa.Column('nma_PointID', sa.String(length=10), nullable=True))
    op.add_column('NMA_AssociatedData', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.drop_constraint(op.f('AssociatedData$LocationId'), 'NMA_AssociatedData', type_='unique')
    op.drop_index(op.f('AssociatedData$PointID'), table_name='NMA_AssociatedData')
    op.drop_constraint(op.f('NMA_AssociatedData_OBJECTID_key'), 'NMA_AssociatedData', type_='unique')
    op.create_unique_constraint(None, 'NMA_AssociatedData', ['nma_LocationId'])
    op.create_unique_constraint(None, 'NMA_AssociatedData', ['nma_AssocID'])
    op.create_unique_constraint(None, 'NMA_AssociatedData', ['nma_OBJECTID'])
    op.drop_column('NMA_AssociatedData', 'OBJECTID')
    op.drop_column('NMA_AssociatedData', 'LocationId')
    op.drop_column('NMA_AssociatedData', 'AssocID')
    op.drop_column('NMA_AssociatedData', 'PointID')

    # --- NMA_HydraulicsData ---
    op.add_column('NMA_HydraulicsData', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_HydraulicsData', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_HydraulicsData', sa.Column('nma_WellID', sa.UUID(), nullable=True))
    op.add_column('NMA_HydraulicsData', sa.Column('nma_PointID', sa.String(length=50), nullable=True))
    op.add_column('NMA_HydraulicsData', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.drop_index(op.f('ix_nma_hydraulicsdata_objectid'), table_name='NMA_HydraulicsData')
    op.drop_index(op.f('ix_nma_hydraulicsdata_pointid'), table_name='NMA_HydraulicsData')
    op.drop_index(op.f('ix_nma_hydraulicsdata_wellid'), table_name='NMA_HydraulicsData')
    op.create_unique_constraint(None, 'NMA_HydraulicsData', ['nma_GlobalID'])
    op.create_unique_constraint(None, 'NMA_HydraulicsData', ['nma_OBJECTID'])
    op.drop_column('NMA_HydraulicsData', 'WellID')
    op.drop_column('NMA_HydraulicsData', 'OBJECTID')
    op.drop_column('NMA_HydraulicsData', 'PointID')
    op.drop_column('NMA_HydraulicsData', 'GlobalID')

    # --- NMA_MajorChemistry ---
    op.add_column('NMA_MajorChemistry', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_MajorChemistry', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('chemistry_sample_info_id', sa.Integer(), nullable=False))
    op.add_column('NMA_MajorChemistry', sa.Column('nma_SamplePtID', sa.UUID(), nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('nma_SamplePointID', sa.String(length=10), nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('nma_WCLab_ID', sa.String(length=25), nullable=True))
    op.drop_index(op.f('MajorChemistry$AnalysesAgency'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$Analyte'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$Chemistry SampleInfoMajorChemistry'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$SamplePointID'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$SamplePointIDAnalyte'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$SamplePtID'), table_name='NMA_MajorChemistry')
    op.drop_index(op.f('MajorChemistry$WCLab_ID'), table_name='NMA_MajorChemistry')
    op.drop_constraint(op.f('NMA_MajorChemistry_OBJECTID_key'), 'NMA_MajorChemistry', type_='unique')
    op.create_unique_constraint(None, 'NMA_MajorChemistry', ['nma_GlobalID'])
    op.create_unique_constraint(None, 'NMA_MajorChemistry', ['nma_OBJECTID'])
    op.create_foreign_key(None, 'NMA_MajorChemistry', 'NMA_Chemistry_SampleInfo', ['chemistry_sample_info_id'], ['id'], ondelete='CASCADE')
    op.drop_column('NMA_MajorChemistry', 'SamplePointID')
    op.drop_column('NMA_MajorChemistry', 'SamplePtID')
    op.drop_column('NMA_MajorChemistry', 'WCLab_ID')
    op.drop_column('NMA_MajorChemistry', 'OBJECTID')
    op.drop_column('NMA_MajorChemistry', 'GlobalID')

    # --- NMA_MinorTraceChemistry ---
    op.add_column('NMA_MinorTraceChemistry', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_MinorTraceChemistry', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_MinorTraceChemistry', sa.Column('nma_chemistry_sample_info_uuid', sa.UUID(), nullable=True))
    op.alter_column('NMA_MinorTraceChemistry', 'chemistry_sample_info_id',
               existing_type=sa.UUID(),
               type_=sa.Integer(),
               nullable=False,
               postgresql_using='NULL')
    op.create_unique_constraint(None, 'NMA_MinorTraceChemistry', ['nma_GlobalID'])
    op.create_foreign_key(None, 'NMA_MinorTraceChemistry', 'NMA_Chemistry_SampleInfo', ['chemistry_sample_info_id'], ['id'], ondelete='CASCADE')
    op.drop_column('NMA_MinorTraceChemistry', 'GlobalID')

    # --- NMA_Radionuclides ---
    op.add_column('NMA_Radionuclides', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_Radionuclides', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('chemistry_sample_info_id', sa.Integer(), nullable=False))
    op.add_column('NMA_Radionuclides', sa.Column('nma_SamplePtID', sa.UUID(), nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('nma_SamplePointID', sa.String(length=10), nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('nma_WCLab_ID', sa.String(length=25), nullable=True))
    op.drop_constraint(op.f('NMA_Radionuclides_OBJECTID_key'), 'NMA_Radionuclides', type_='unique')
    op.drop_index(op.f('Radionuclides$AnalysesAgency'), table_name='NMA_Radionuclides')
    op.drop_index(op.f('Radionuclides$Analyte'), table_name='NMA_Radionuclides')
    op.drop_index(op.f('Radionuclides$Chemistry SampleInfoRadionuclides'), table_name='NMA_Radionuclides')
    op.drop_index(op.f('Radionuclides$SamplePointID'), table_name='NMA_Radionuclides')
    op.drop_index(op.f('Radionuclides$SamplePtID'), table_name='NMA_Radionuclides')
    op.drop_index(op.f('Radionuclides$WCLab_ID'), table_name='NMA_Radionuclides')
    op.create_unique_constraint(None, 'NMA_Radionuclides', ['nma_GlobalID'])
    op.create_unique_constraint(None, 'NMA_Radionuclides', ['nma_OBJECTID'])
    op.create_foreign_key(None, 'NMA_Radionuclides', 'NMA_Chemistry_SampleInfo', ['chemistry_sample_info_id'], ['id'], ondelete='CASCADE')
    op.drop_column('NMA_Radionuclides', 'SamplePointID')
    op.drop_column('NMA_Radionuclides', 'SamplePtID')
    op.drop_column('NMA_Radionuclides', 'WCLab_ID')
    op.drop_column('NMA_Radionuclides', 'OBJECTID')
    op.drop_column('NMA_Radionuclides', 'GlobalID')

    # --- NMA_Soil_Rock_Results ---
    op.add_column('NMA_Soil_Rock_Results', sa.Column('nma_Point_ID', sa.String(length=255), nullable=True))
    op.drop_index(op.f('Soil_Rock_Results$Point_ID'), table_name='NMA_Soil_Rock_Results')
    op.drop_column('NMA_Soil_Rock_Results', 'Point_ID')

    # --- NMA_Stratigraphy ---
    op.add_column('NMA_Stratigraphy', sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1), nullable=False))
    op.add_column('NMA_Stratigraphy', sa.Column('nma_GlobalID', sa.UUID(), nullable=True))
    op.add_column('NMA_Stratigraphy', sa.Column('nma_WellID', sa.UUID(), nullable=True))
    op.add_column('NMA_Stratigraphy', sa.Column('nma_PointID', sa.String(length=10), nullable=False))
    op.add_column('NMA_Stratigraphy', sa.Column('nma_OBJECTID', sa.Integer(), nullable=True))
    op.drop_constraint(op.f('NMA_Stratigraphy_OBJECTID_key'), 'NMA_Stratigraphy', type_='unique')
    op.drop_index(op.f('ix_nma_stratigraphy_point_id'), table_name='NMA_Stratigraphy')
    op.drop_index(op.f('ix_nma_stratigraphy_thing_id'), table_name='NMA_Stratigraphy')
    op.create_unique_constraint(None, 'NMA_Stratigraphy', ['nma_GlobalID'])
    op.create_unique_constraint(None, 'NMA_Stratigraphy', ['nma_OBJECTID'])
    op.drop_column('NMA_Stratigraphy', 'OBJECTID')
    op.drop_column('NMA_Stratigraphy', 'WellID')
    op.drop_column('NMA_Stratigraphy', 'PointID')
    op.drop_column('NMA_Stratigraphy', 'GlobalID')

    # --- Other tables (index/constraint cleanup from autogenerate) ---
    op.drop_index(op.f('SurfaceWaterPhotos$PointID'), table_name='NMA_SurfaceWaterPhotos')
    op.drop_index(op.f('SurfaceWaterPhotos$SurfaceID'), table_name='NMA_SurfaceWaterPhotos')
    op.drop_constraint(op.f('uq_nma_pressure_daily_globalid'), 'NMA_WaterLevelsContinuous_Pressure_Daily', type_='unique')
    op.drop_index(op.f('WeatherPhotos$PointID'), table_name='NMA_WeatherPhotos')
    op.drop_index(op.f('WeatherPhotos$WeatherID'), table_name='NMA_WeatherPhotos')
    op.alter_column('NMA_view_NGWMN_Lithology', 'PointID',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
    op.drop_constraint(op.f('uq_nma_view_ngwmn_lithology_objectid'), 'NMA_view_NGWMN_Lithology', type_='unique')
    op.drop_constraint(op.f('uq_nma_view_ngwmn_waterlevels_point_date'), 'NMA_view_NGWMN_WaterLevels', type_='unique')
    op.alter_column('NMA_view_NGWMN_WellConstruction', 'PointID',
               existing_type=sa.VARCHAR(length=50),
               nullable=False)
    op.drop_constraint(op.f('uq_nma_view_ngwmn_wellconstruction_point_casing_screen'), 'NMA_view_NGWMN_WellConstruction', type_='unique')
    op.alter_column('thing', 'nma_formation_zone',
               existing_type=sa.VARCHAR(length=25),
               comment='Raw FormationZone value from legacy WellData (NM_Aquifer).',
               existing_nullable=True)
    op.alter_column('thing_version', 'nma_pk_location',
               existing_type=sa.VARCHAR(),
               comment='To audit the original NM_Aquifer LocationID if it was transferred over',
               existing_nullable=True,
               autoincrement=False)
    op.alter_column('thing_version', 'nma_formation_zone',
               existing_type=sa.VARCHAR(length=25),
               comment='Raw FormationZone value from legacy WellData (NM_Aquifer).',
               existing_nullable=True,
               autoincrement=False)
    op.alter_column('transducer_observation', 'nma_waterlevelscontinuous_pressure_created',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)
    op.alter_column('transducer_observation', 'nma_waterlevelscontinuous_pressure_updated',
               existing_type=postgresql.TIMESTAMP(),
               type_=sa.DateTime(timezone=True),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('transducer_observation', 'nma_waterlevelscontinuous_pressure_updated',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('transducer_observation', 'nma_waterlevelscontinuous_pressure_created',
               existing_type=sa.DateTime(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('thing_version', 'nma_formation_zone',
               existing_type=sa.VARCHAR(length=25),
               comment=None,
               existing_comment='Raw FormationZone value from legacy WellData (NM_Aquifer).',
               existing_nullable=True,
               autoincrement=False)
    op.alter_column('thing_version', 'nma_pk_location',
               existing_type=sa.VARCHAR(),
               comment=None,
               existing_comment='To audit the original NM_Aquifer LocationID if it was transferred over',
               existing_nullable=True,
               autoincrement=False)
    op.alter_column('thing', 'nma_formation_zone',
               existing_type=sa.VARCHAR(length=25),
               comment=None,
               existing_comment='Raw FormationZone value from legacy WellData (NM_Aquifer).',
               existing_nullable=True)
    op.create_unique_constraint(op.f('uq_nma_view_ngwmn_wellconstruction_point_casing_screen'), 'NMA_view_NGWMN_WellConstruction', ['PointID', 'CasingTop', 'ScreenTop'], postgresql_nulls_not_distinct=False)
    op.alter_column('NMA_view_NGWMN_WellConstruction', 'PointID',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
    op.create_unique_constraint(op.f('uq_nma_view_ngwmn_waterlevels_point_date'), 'NMA_view_NGWMN_WaterLevels', ['PointID', 'DateMeasured'], postgresql_nulls_not_distinct=False)
    op.create_unique_constraint(op.f('uq_nma_view_ngwmn_lithology_objectid'), 'NMA_view_NGWMN_Lithology', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.alter_column('NMA_view_NGWMN_Lithology', 'PointID',
               existing_type=sa.VARCHAR(length=50),
               nullable=True)
    op.create_index(op.f('WeatherPhotos$WeatherID'), 'NMA_WeatherPhotos', ['WeatherID'], unique=False)
    op.create_index(op.f('WeatherPhotos$PointID'), 'NMA_WeatherPhotos', ['PointID'], unique=False)
    op.create_unique_constraint(op.f('uq_nma_pressure_daily_globalid'), 'NMA_WaterLevelsContinuous_Pressure_Daily', ['GlobalID'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('SurfaceWaterPhotos$SurfaceID'), 'NMA_SurfaceWaterPhotos', ['SurfaceID'], unique=False)
    op.create_index(op.f('SurfaceWaterPhotos$PointID'), 'NMA_SurfaceWaterPhotos', ['PointID'], unique=False)
    op.add_column('NMA_Stratigraphy', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_Stratigraphy', sa.Column('PointID', sa.VARCHAR(length=10), autoincrement=False, nullable=False))
    op.add_column('NMA_Stratigraphy', sa.Column('WellID', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('NMA_Stratigraphy', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_Stratigraphy', type_='unique')
    op.drop_constraint(None, 'NMA_Stratigraphy', type_='unique')
    op.create_index(op.f('ix_nma_stratigraphy_thing_id'), 'NMA_Stratigraphy', ['thing_id'], unique=False)
    op.create_index(op.f('ix_nma_stratigraphy_point_id'), 'NMA_Stratigraphy', ['PointID'], unique=False)
    op.create_unique_constraint(op.f('NMA_Stratigraphy_OBJECTID_key'), 'NMA_Stratigraphy', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.drop_column('NMA_Stratigraphy', 'nma_OBJECTID')
    op.drop_column('NMA_Stratigraphy', 'nma_PointID')
    op.drop_column('NMA_Stratigraphy', 'nma_WellID')
    op.drop_column('NMA_Stratigraphy', 'nma_GlobalID')
    op.drop_column('NMA_Stratigraphy', 'id')
    op.add_column('NMA_Soil_Rock_Results', sa.Column('Point_ID', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.create_index(op.f('Soil_Rock_Results$Point_ID'), 'NMA_Soil_Rock_Results', ['Point_ID'], unique=False)
    op.drop_column('NMA_Soil_Rock_Results', 'nma_Point_ID')
    op.add_column('NMA_Radionuclides', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_Radionuclides', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('WCLab_ID', sa.VARCHAR(length=25), autoincrement=False, nullable=True))
    op.add_column('NMA_Radionuclides', sa.Column('SamplePtID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_Radionuclides', sa.Column('SamplePointID', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_Radionuclides', type_='foreignkey')
    op.create_foreign_key(op.f('NMA_Radionuclides_SamplePtID_fkey'), 'NMA_Radionuclides', 'NMA_Chemistry_SampleInfo', ['SamplePtID'], ['SamplePtID'], ondelete='CASCADE')
    op.drop_constraint(None, 'NMA_Radionuclides', type_='unique')
    op.drop_constraint(None, 'NMA_Radionuclides', type_='unique')
    op.create_index(op.f('Radionuclides$WCLab_ID'), 'NMA_Radionuclides', ['WCLab_ID'], unique=False)
    op.create_index(op.f('Radionuclides$SamplePtID'), 'NMA_Radionuclides', ['SamplePtID'], unique=False)
    op.create_index(op.f('Radionuclides$SamplePointID'), 'NMA_Radionuclides', ['SamplePointID'], unique=False)
    op.create_index(op.f('Radionuclides$Chemistry SampleInfoRadionuclides'), 'NMA_Radionuclides', ['SamplePtID'], unique=False)
    op.create_index(op.f('Radionuclides$Analyte'), 'NMA_Radionuclides', ['Analyte'], unique=False)
    op.create_index(op.f('Radionuclides$AnalysesAgency'), 'NMA_Radionuclides', ['AnalysesAgency'], unique=False)
    op.create_unique_constraint(op.f('NMA_Radionuclides_OBJECTID_key'), 'NMA_Radionuclides', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.drop_column('NMA_Radionuclides', 'nma_WCLab_ID')
    op.drop_column('NMA_Radionuclides', 'nma_OBJECTID')
    op.drop_column('NMA_Radionuclides', 'nma_SamplePointID')
    op.drop_column('NMA_Radionuclides', 'nma_SamplePtID')
    op.drop_column('NMA_Radionuclides', 'chemistry_sample_info_id')
    op.drop_column('NMA_Radionuclides', 'nma_GlobalID')
    op.drop_column('NMA_Radionuclides', 'id')
    op.add_column('NMA_MinorTraceChemistry', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'NMA_MinorTraceChemistry', type_='foreignkey')
    op.create_foreign_key(op.f('NMA_MinorTraceChemistry_chemistry_sample_info_id_fkey'), 'NMA_MinorTraceChemistry', 'NMA_Chemistry_SampleInfo', ['chemistry_sample_info_id'], ['SamplePtID'], ondelete='CASCADE')
    op.drop_constraint(None, 'NMA_MinorTraceChemistry', type_='unique')
    op.alter_column('NMA_MinorTraceChemistry', 'chemistry_sample_info_id',
               existing_type=sa.Integer(),
               type_=sa.UUID(),
               existing_nullable=False)
    op.drop_column('NMA_MinorTraceChemistry', 'nma_chemistry_sample_info_uuid')
    op.drop_column('NMA_MinorTraceChemistry', 'nma_GlobalID')
    op.drop_column('NMA_MinorTraceChemistry', 'id')
    op.add_column('NMA_MajorChemistry', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_MajorChemistry', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('WCLab_ID', sa.VARCHAR(length=25), autoincrement=False, nullable=True))
    op.add_column('NMA_MajorChemistry', sa.Column('SamplePtID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_MajorChemistry', sa.Column('SamplePointID', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_MajorChemistry', type_='foreignkey')
    op.create_foreign_key(op.f('NMA_MajorChemistry_SamplePtID_fkey'), 'NMA_MajorChemistry', 'NMA_Chemistry_SampleInfo', ['SamplePtID'], ['SamplePtID'], ondelete='CASCADE')
    op.drop_constraint(None, 'NMA_MajorChemistry', type_='unique')
    op.drop_constraint(None, 'NMA_MajorChemistry', type_='unique')
    op.create_unique_constraint(op.f('NMA_MajorChemistry_OBJECTID_key'), 'NMA_MajorChemistry', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('MajorChemistry$WCLab_ID'), 'NMA_MajorChemistry', ['WCLab_ID'], unique=False)
    op.create_index(op.f('MajorChemistry$SamplePtID'), 'NMA_MajorChemistry', ['SamplePtID'], unique=False)
    op.create_index(op.f('MajorChemistry$SamplePointIDAnalyte'), 'NMA_MajorChemistry', ['SamplePointID', 'Analyte'], unique=False)
    op.create_index(op.f('MajorChemistry$SamplePointID'), 'NMA_MajorChemistry', ['SamplePointID'], unique=False)
    op.create_index(op.f('MajorChemistry$Chemistry SampleInfoMajorChemistry'), 'NMA_MajorChemistry', ['SamplePtID'], unique=False)
    op.create_index(op.f('MajorChemistry$Analyte'), 'NMA_MajorChemistry', ['Analyte'], unique=False)
    op.create_index(op.f('MajorChemistry$AnalysesAgency'), 'NMA_MajorChemistry', ['AnalysesAgency'], unique=False)
    op.drop_column('NMA_MajorChemistry', 'nma_WCLab_ID')
    op.drop_column('NMA_MajorChemistry', 'nma_OBJECTID')
    op.drop_column('NMA_MajorChemistry', 'nma_SamplePointID')
    op.drop_column('NMA_MajorChemistry', 'nma_SamplePtID')
    op.drop_column('NMA_MajorChemistry', 'chemistry_sample_info_id')
    op.drop_column('NMA_MajorChemistry', 'nma_GlobalID')
    op.drop_column('NMA_MajorChemistry', 'id')
    op.add_column('NMA_HydraulicsData', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_HydraulicsData', sa.Column('PointID', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('NMA_HydraulicsData', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('NMA_HydraulicsData', sa.Column('WellID', sa.UUID(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_HydraulicsData', type_='unique')
    op.drop_constraint(None, 'NMA_HydraulicsData', type_='unique')
    op.create_index(op.f('ix_nma_hydraulicsdata_wellid'), 'NMA_HydraulicsData', ['WellID'], unique=False)
    op.create_index(op.f('ix_nma_hydraulicsdata_pointid'), 'NMA_HydraulicsData', ['PointID'], unique=False)
    op.create_index(op.f('ix_nma_hydraulicsdata_objectid'), 'NMA_HydraulicsData', ['OBJECTID'], unique=True)
    op.drop_column('NMA_HydraulicsData', 'nma_OBJECTID')
    op.drop_column('NMA_HydraulicsData', 'nma_PointID')
    op.drop_column('NMA_HydraulicsData', 'nma_WellID')
    op.drop_column('NMA_HydraulicsData', 'nma_GlobalID')
    op.drop_column('NMA_HydraulicsData', 'id')
    op.add_column('NMA_FieldParameters', sa.Column('GlobalID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_FieldParameters', sa.Column('OBJECTID', sa.INTEGER(), sa.Identity(always=False, start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), autoincrement=True, nullable=False))
    op.add_column('NMA_FieldParameters', sa.Column('WCLab_ID', sa.VARCHAR(length=25), autoincrement=False, nullable=True))
    op.add_column('NMA_FieldParameters', sa.Column('SamplePtID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_FieldParameters', sa.Column('SamplePointID', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_FieldParameters', type_='foreignkey')
    op.create_foreign_key(op.f('NMA_FieldParameters_SamplePtID_fkey'), 'NMA_FieldParameters', 'NMA_Chemistry_SampleInfo', ['SamplePtID'], ['SamplePtID'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_constraint(None, 'NMA_FieldParameters', type_='unique')
    op.drop_index('FieldParameters$nma_WCLab_ID', table_name='NMA_FieldParameters')
    op.drop_index('FieldParameters$nma_SamplePointID', table_name='NMA_FieldParameters')
    op.drop_index('FieldParameters$nma_OBJECTID', table_name='NMA_FieldParameters')
    op.drop_index('FieldParameters$nma_GlobalID', table_name='NMA_FieldParameters')
    op.drop_index('FieldParameters$ChemistrySampleInfoFieldParameters', table_name='NMA_FieldParameters')
    op.create_index(op.f('FieldParameters$ChemistrySampleInfoFieldParameters'), 'NMA_FieldParameters', ['SamplePtID'], unique=False)
    op.create_index(op.f('FieldParameters$WCLab_ID'), 'NMA_FieldParameters', ['WCLab_ID'], unique=False)
    op.create_index(op.f('FieldParameters$SamplePtID'), 'NMA_FieldParameters', ['SamplePtID'], unique=False)
    op.create_index(op.f('FieldParameters$SamplePointID'), 'NMA_FieldParameters', ['SamplePointID'], unique=False)
    op.create_index(op.f('FieldParameters$OBJECTID'), 'NMA_FieldParameters', ['OBJECTID'], unique=True)
    op.create_index(op.f('FieldParameters$GlobalID'), 'NMA_FieldParameters', ['GlobalID'], unique=True)
    op.drop_column('NMA_FieldParameters', 'nma_WCLab_ID')
    op.drop_column('NMA_FieldParameters', 'nma_OBJECTID')
    op.drop_column('NMA_FieldParameters', 'nma_SamplePointID')
    op.drop_column('NMA_FieldParameters', 'nma_SamplePtID')
    op.drop_column('NMA_FieldParameters', 'chemistry_sample_info_id')
    op.drop_column('NMA_FieldParameters', 'nma_GlobalID')
    op.drop_column('NMA_FieldParameters', 'id')
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('LocationId', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('WCLab_ID', sa.VARCHAR(length=18), autoincrement=False, nullable=True))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('SamplePtID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_Chemistry_SampleInfo', sa.Column('SamplePointID', sa.VARCHAR(length=10), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'NMA_Chemistry_SampleInfo', type_='unique')
    op.drop_constraint(None, 'NMA_Chemistry_SampleInfo', type_='unique')
    op.create_unique_constraint(op.f('NMA_Chemistry_SampleInfo_OBJECTID_key'), 'NMA_Chemistry_SampleInfo', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.drop_column('NMA_Chemistry_SampleInfo', 'nma_LocationId')
    op.drop_column('NMA_Chemistry_SampleInfo', 'nma_OBJECTID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'nma_SamplePointID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'nma_WCLab_ID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'nma_SamplePtID')
    op.drop_column('NMA_Chemistry_SampleInfo', 'id')
    op.add_column('NMA_AssociatedData', sa.Column('PointID', sa.VARCHAR(length=10), autoincrement=False, nullable=True))
    op.add_column('NMA_AssociatedData', sa.Column('AssocID', sa.UUID(), autoincrement=False, nullable=False))
    op.add_column('NMA_AssociatedData', sa.Column('LocationId', sa.UUID(), autoincrement=False, nullable=True))
    op.add_column('NMA_AssociatedData', sa.Column('OBJECTID', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'NMA_AssociatedData', type_='unique')
    op.drop_constraint(None, 'NMA_AssociatedData', type_='unique')
    op.drop_constraint(None, 'NMA_AssociatedData', type_='unique')
    op.create_unique_constraint(op.f('NMA_AssociatedData_OBJECTID_key'), 'NMA_AssociatedData', ['OBJECTID'], postgresql_nulls_not_distinct=False)
    op.create_index(op.f('AssociatedData$PointID'), 'NMA_AssociatedData', ['PointID'], unique=False)
    op.create_unique_constraint(op.f('AssociatedData$LocationId'), 'NMA_AssociatedData', ['LocationId'], postgresql_nulls_not_distinct=False)
    op.drop_column('NMA_AssociatedData', 'nma_OBJECTID')
    op.drop_column('NMA_AssociatedData', 'nma_PointID')
    op.drop_column('NMA_AssociatedData', 'nma_LocationId')
    op.drop_column('NMA_AssociatedData', 'nma_AssocID')
    op.drop_column('NMA_AssociatedData', 'id')
