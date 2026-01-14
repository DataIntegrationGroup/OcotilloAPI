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
Unit tests for SurfaceWaterData legacy model.

These tests verify the migration of columns from the legacy SurfaceWaterData table.
Migrated columns:
- SurfaceID -> surface_id
- PointID -> point_id
- OBJECTID -> object_id
- Discharge -> discharge
- DischargeMethod -> discharge_method
- DischargeRate -> discharge_rate
- DischargeUnits -> discharge_units
- DateMeasured -> date_measured
- DischargeSource -> discharge_source
- SiteNotes -> site_notes
- FieldMethodNotes -> field_method_notes
- FormationZone -> formation_zone
- AqClass -> aq_class
- SourceNotes -> source_notes
- DataSource -> data_source
"""

from datetime import datetime
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import SurfaceWaterData


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


# ===================== CREATE tests ==========================
def test_create_surface_water_data_all_fields():
    """Test creating a surface water data record with all fields."""
    with session_ctx() as session:
        record = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1001",
            object_id=_next_object_id(),
            discharge="1.2",
            discharge_method="Method A",
            discharge_rate=1.2,
            discharge_units="cfs",
            date_measured=datetime(2024, 1, 1, 12, 0, 0),
            discharge_source="Source A",
            site_notes="Site notes",
            field_method_notes="Field notes",
            formation_zone="FZ",
            aq_class="Class A",
            source_notes="Source notes",
            data_source="SRC",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.object_id is not None
        assert record.point_id == "SW-1001"
        assert record.surface_id is not None
        assert record.discharge_rate == 1.2

        session.delete(record)
        session.commit()


def test_create_surface_water_data_minimal():
    """Test creating a surface water data record with minimal fields."""
    with session_ctx() as session:
        record = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1002",
            object_id=_next_object_id(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.object_id is not None
        assert record.point_id == "SW-1002"
        assert record.surface_id is not None
        assert record.discharge is None

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_surface_water_data_by_object_id():
    """Test reading a surface water data record by OBJECTID."""
    with session_ctx() as session:
        record = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1003",
            object_id=_next_object_id(),
        )
        session.add(record)
        session.commit()

        fetched = session.get(SurfaceWaterData, record.object_id)
        assert fetched is not None
        assert fetched.object_id == record.object_id
        assert fetched.point_id == "SW-1003"

        session.delete(record)
        session.commit()


def test_query_surface_water_data_by_point_id():
    """Test querying surface water data by point_id."""
    with session_ctx() as session:
        record1 = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1004",
            object_id=_next_object_id(),
        )
        record2 = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1005",
            object_id=_next_object_id(),
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(SurfaceWaterData)
            .filter(SurfaceWaterData.point_id == "SW-1004")
            .all()
        )
        assert len(results) >= 1
        assert all(r.point_id == "SW-1004" for r in results)

        session.delete(record1)
        session.delete(record2)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_surface_water_data():
    """Test updating a surface water data record."""
    with session_ctx() as session:
        record = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1006",
            object_id=_next_object_id(),
        )
        session.add(record)
        session.commit()

        record.discharge_rate = 2.5
        record.discharge_units = "cms"
        session.commit()
        session.refresh(record)

        assert record.discharge_rate == 2.5
        assert record.discharge_units == "cms"

        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_surface_water_data():
    """Test deleting a surface water data record."""
    with session_ctx() as session:
        record = SurfaceWaterData(
            surface_id=uuid4(),
            point_id="SW-1007",
            object_id=_next_object_id(),
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(SurfaceWaterData, record.object_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_surface_water_data_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "surface_id",
        "point_id",
        "object_id",
        "discharge",
        "discharge_method",
        "discharge_rate",
        "discharge_units",
        "date_measured",
        "discharge_source",
        "site_notes",
        "field_method_notes",
        "formation_zone",
        "aq_class",
        "source_notes",
        "data_source",
    ]

    for column in expected_columns:
        assert hasattr(
            SurfaceWaterData, column
        ), f"Expected column '{column}' not found in SurfaceWaterData model"


def test_surface_water_data_table_name():
    """Test that the table name follows convention."""
    assert SurfaceWaterData.__tablename__ == "NMA_SurfaceWaterData"


# ============= EOF =============================================
