# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
"""
Unit tests for HydraulicsData legacy model.

These tests verify the migration of columns from the legacy HydraulicsData table.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy GlobalID UUID (UNIQUE)
- nma_well_id: Legacy WellID UUID
- nma_point_id: Legacy PointID string
- nma_object_id: Legacy OBJECTID (UNIQUE)
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_HydraulicsData


def _next_global_id():
    return uuid4()


# ===================== CREATE tests ==========================
def test_create_hydraulics_data_all_fields(water_well_thing):
    """Test creating a hydraulics data record with all fields."""
    with session_ctx() as session:
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            nma_well_id=uuid4(),
            nma_point_id=water_well_thing.name,
            data_source="Legacy Source",
            cs_gal_d_ft=1.2,
            hd_ft2_d=3.4,
            hl_day_1=0.02,
            kh_ft_d=12.5,
            kv_ft_d=1.1,
            p_decimal_fraction=0.15,
            s_dimensionless=0.2,
            ss_ft_1=0.003,
            sy_decimalfractn=0.12,
            t_ft2_d=45.6,
            k_darcy=2.5,
            test_bottom=120,
            test_top=30,
            hydraulic_unit="Unit A",
            hydraulic_unit_type="U",
            hydraulic_remarks="Test remarks",
            nma_object_id=101,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.nma_well_id is not None
        assert record.nma_point_id == water_well_thing.name
        assert record.data_source == "Legacy Source"
        assert record.test_top == 30
        assert record.test_bottom == 120
        assert record.nma_object_id == 101
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


def test_create_hydraulics_data_minimal(water_well_thing):
    """Test creating a hydraulics data record with minimal fields."""
    with session_ctx() as session:
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=10,
            test_bottom=20,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.nma_well_id is None
        assert record.nma_point_id is None
        assert record.data_source is None
        assert record.nma_object_id is None
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_hydraulics_data_by_id(water_well_thing):
    """Test reading a hydraulics data record by Integer ID."""
    with session_ctx() as session:
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_HydraulicsData, record.id)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.nma_global_id == record.nma_global_id

        session.delete(record)
        session.commit()


def test_query_hydraulics_data_by_nma_point_id(water_well_thing):
    """Test querying hydraulics data by nma_point_id."""
    with session_ctx() as session:
        record1 = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            nma_well_id=uuid4(),
            nma_point_id=water_well_thing.name,
            test_top=10,
            test_bottom=20,
            thing_id=water_well_thing.id,
        )
        record2 = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            nma_point_id="OTHER-POINT",
            test_top=30,
            test_bottom=40,
            thing_id=water_well_thing.id,
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(NMA_HydraulicsData)
            .filter(NMA_HydraulicsData.nma_point_id == water_well_thing.name)
            .all()
        )
        assert len(results) >= 1
        assert all(r.nma_point_id == water_well_thing.name for r in results)

        session.delete(record1)
        session.delete(record2)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_hydraulics_data(water_well_thing):
    """Test updating a hydraulics data record."""
    with session_ctx() as session:
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        record.hydraulic_remarks = "Updated remarks"
        record.data_source = "Updated source"
        session.commit()
        session.refresh(record)

        assert record.hydraulic_remarks == "Updated remarks"
        assert record.data_source == "Updated source"

        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_hydraulics_data(water_well_thing):
    """Test deleting a hydraulics data record."""
    with session_ctx() as session:
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        record_id = record.id

        session.delete(record)
        session.commit()

        fetched = session.get(NMA_HydraulicsData, record_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_hydraulics_data_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "id",
        "nma_global_id",
        "nma_well_id",
        "nma_point_id",
        "data_source",
        "cs_gal_d_ft",
        "hd_ft2_d",
        "hl_day_1",
        "kh_ft_d",
        "kv_ft_d",
        "p_decimal_fraction",
        "s_dimensionless",
        "ss_ft_1",
        "sy_decimalfractn",
        "t_ft2_d",
        "k_darcy",
        "test_bottom",
        "test_top",
        "hydraulic_unit",
        "hydraulic_unit_type",
        "hydraulic_remarks",
        "nma_object_id",
        "thing_id",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_HydraulicsData, column
        ), f"Expected column '{column}' not found in NMA_HydraulicsData model"


def test_hydraulics_data_table_name():
    """Test that the table name follows convention."""
    assert NMA_HydraulicsData.__tablename__ == "NMA_HydraulicsData"


# ===================== FK Enforcement tests (Issue #363) ==========================


def test_hydraulics_data_validator_rejects_none_thing_id():
    """NMA_HydraulicsData validator rejects None thing_id."""
    import pytest

    with pytest.raises(ValueError, match="requires a parent Thing"):
        NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=None,
        )


def test_hydraulics_data_thing_id_not_nullable():
    """NMA_HydraulicsData.thing_id column is NOT NULL."""
    col = NMA_HydraulicsData.__table__.c.thing_id
    assert col.nullable is False, "thing_id should be NOT NULL"


def test_hydraulics_data_fk_has_cascade():
    """NMA_HydraulicsData.thing_id FK has ondelete=CASCADE."""
    col = NMA_HydraulicsData.__table__.c.thing_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_hydraulics_data_back_populates_thing(water_well_thing):
    """NMA_HydraulicsData.thing navigates back to Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_HydraulicsData(
            nma_global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=well.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.thing is not None
        assert record.thing.id == well.id

        session.delete(record)
        session.commit()


# ===================== Integer PK tests ==========================


def test_hydraulics_data_has_integer_pk():
    """NMA_HydraulicsData.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_HydraulicsData.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_hydraulics_data_nma_global_id_is_unique():
    """NMA_HydraulicsData.nma_global_id is UNIQUE."""
    col = NMA_HydraulicsData.__table__.c.nma_global_id
    assert col.unique is True


# ============= EOF =============================================
