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
Migrated columns:
- GlobalID -> global_id
- WellID -> well_id
- PointID -> point_id
- Data Source -> data_source
- Cs (gal/d/ft) -> cs_gal_d_ft
- HD (ft2/d) -> hd_ft2_d
- HL (day-1) -> hl_day_1
- KH (ft/d) -> kh_ft_d
- KV (ft/d) -> kv_ft_d
- P (decimal fraction) -> p_decimal_fraction
- S (dimensionless) -> s_dimensionless
- Ss (ft-1) -> ss_ft_1
- Sy (decimalfractn) -> sy_decimalfractn
- T (ft2/d) -> t_ft2_d
- k (darcy) -> k_darcy
- TestBottom -> test_bottom
- TestTop -> test_top
- HydraulicUnit -> hydraulic_unit
- HydraulicUnitType -> hydraulic_unit_type
- Hydraulic Remarks -> hydraulic_remarks
- OBJECTID -> object_id
- thing_id -> thing_id
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMAHydraulicsData


def _next_global_id():
    return uuid4()


# ===================== CREATE tests ==========================
def test_create_hydraulics_data_all_fields(water_well_thing):
    """Test creating a hydraulics data record with all fields."""
    with session_ctx() as session:
        record = NMAHydraulicsData(
            global_id=_next_global_id(),
            well_id=uuid4(),
            point_id=water_well_thing.name,
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
            object_id=101,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.well_id is not None
        assert record.point_id == water_well_thing.name
        assert record.data_source == "Legacy Source"
        assert record.test_top == 30
        assert record.test_bottom == 120
        assert record.object_id == 101
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


def test_create_hydraulics_data_minimal(water_well_thing):
    """Test creating a hydraulics data record with minimal fields."""
    with session_ctx() as session:
        record = NMAHydraulicsData(
            global_id=_next_global_id(),
            test_top=10,
            test_bottom=20,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.well_id is None
        assert record.point_id is None
        assert record.data_source is None
        assert record.object_id is None
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_hydraulics_data_by_global_id(water_well_thing):
    """Test reading a hydraulics data record by GlobalID."""
    with session_ctx() as session:
        record = NMAHydraulicsData(
            global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMAHydraulicsData, record.global_id)
        assert fetched is not None
        assert fetched.global_id == record.global_id

        session.delete(record)
        session.commit()


def test_query_hydraulics_data_by_point_id(water_well_thing):
    """Test querying hydraulics data by point_id."""
    with session_ctx() as session:
        record1 = NMAHydraulicsData(
            global_id=_next_global_id(),
            well_id=uuid4(),
            point_id=water_well_thing.name,
            test_top=10,
            test_bottom=20,
            thing_id=water_well_thing.id,
        )
        record2 = NMAHydraulicsData(
            global_id=_next_global_id(),
            point_id="OTHER-POINT",
            test_top=30,
            test_bottom=40,
            thing_id=water_well_thing.id,
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(NMAHydraulicsData)
            .filter(NMAHydraulicsData.point_id == water_well_thing.name)
            .all()
        )
        assert len(results) >= 1
        assert all(r.point_id == water_well_thing.name for r in results)

        session.delete(record1)
        session.delete(record2)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_hydraulics_data(water_well_thing):
    """Test updating a hydraulics data record."""
    with session_ctx() as session:
        record = NMAHydraulicsData(
            global_id=_next_global_id(),
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
        record = NMAHydraulicsData(
            global_id=_next_global_id(),
            test_top=5,
            test_bottom=15,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(NMAHydraulicsData, record.global_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_hydraulics_data_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "global_id",
        "well_id",
        "point_id",
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
        "object_id",
        "thing_id",
    ]

    for column in expected_columns:
        assert hasattr(
            NMAHydraulicsData, column
        ), f"Expected column '{column}' not found in NMAHydraulicsData model"


def test_hydraulics_data_table_name():
    """Test that the table name follows convention."""
    assert NMAHydraulicsData.__tablename__ == "NMA_HydraulicsData"


# ============= EOF =============================================
