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
Unit tests for WaterLevelsContinuous_Pressure_Daily legacy model.

These tests verify the migration of columns from the legacy
WaterLevelsContinuous_Pressure_Daily table.
"""

from datetime import datetime
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMAWaterLevelsContinuousPressureDaily


def _next_global_id() -> str:
    return str(uuid4())


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


# ===================== CREATE tests ==========================
def test_create_pressure_daily_all_fields():
    """Test creating a pressure daily record with required fields."""
    with session_ctx() as session:
        now = datetime(2024, 1, 1, 12, 0, 0)
        record = NMAWaterLevelsContinuousPressureDaily(
            global_id=_next_global_id(),
            object_id=_next_object_id(),
            well_id="WELL-1",
            point_id="PD-1001",
            date_measured=now,
            temperature_water=12.3,
            water_head=4.5,
            water_head_adjusted=4.1,
            depth_to_water_bgs=2.3,
            measurement_method="PT",
            data_source="SRC",
            measuring_agency="Agency",
            qced=True,
            notes="Notes",
            created=now,
            updated=now,
            processed_by="AB",
            checked_by="CD",
            cond_dl_ms_cm=0.2,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == "PD-1001"
        assert record.date_measured == now

        session.delete(record)
        session.commit()


def test_create_pressure_daily_minimal():
    """Test creating a pressure daily record with minimal fields."""
    with session_ctx() as session:
        now = datetime(2024, 1, 2, 12, 0, 0)
        record = NMAWaterLevelsContinuousPressureDaily(
            global_id=_next_global_id(),
            point_id="PD-1002",
            date_measured=now,
            created=now,
            updated=now,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == "PD-1002"

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_pressure_daily_by_global_id():
    """Test reading a pressure daily record by GlobalID."""
    with session_ctx() as session:
        now = datetime(2024, 1, 3, 12, 0, 0)
        record = NMAWaterLevelsContinuousPressureDaily(
            global_id=_next_global_id(),
            point_id="PD-1003",
            date_measured=now,
            created=now,
            updated=now,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMAWaterLevelsContinuousPressureDaily, record.global_id)
        assert fetched is not None
        assert fetched.global_id == record.global_id
        assert fetched.point_id == "PD-1003"

        session.delete(record)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_pressure_daily():
    """Test updating a pressure daily record."""
    with session_ctx() as session:
        now = datetime(2024, 1, 4, 12, 0, 0)
        record = NMAWaterLevelsContinuousPressureDaily(
            global_id=_next_global_id(),
            point_id="PD-1004",
            date_measured=now,
            created=now,
            updated=now,
        )
        session.add(record)
        session.commit()

        record.notes = "Updated notes"
        record.qced = False
        session.commit()
        session.refresh(record)

        assert record.notes == "Updated notes"
        assert record.qced is False

        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_pressure_daily():
    """Test deleting a pressure daily record."""
    with session_ctx() as session:
        now = datetime(2024, 1, 5, 12, 0, 0)
        record = NMAWaterLevelsContinuousPressureDaily(
            global_id=_next_global_id(),
            point_id="PD-1005",
            date_measured=now,
            created=now,
            updated=now,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(NMAWaterLevelsContinuousPressureDaily, record.global_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_pressure_daily_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "global_id",
        "object_id",
        "well_id",
        "point_id",
        "date_measured",
        "temperature_water",
        "water_head",
        "water_head_adjusted",
        "depth_to_water_bgs",
        "measurement_method",
        "data_source",
        "measuring_agency",
        "qced",
        "notes",
        "created",
        "updated",
        "processed_by",
        "checked_by",
        "cond_dl_ms_cm",
    ]

    for column in expected_columns:
        assert hasattr(
            NMAWaterLevelsContinuousPressureDaily, column
        ), f"Expected column '{column}' not found in pressure daily model"


def test_pressure_daily_table_name():
    """Test that the table name follows convention."""
    assert (
        NMAWaterLevelsContinuousPressureDaily.__tablename__
        == "NMA_WaterLevelsContinuous_Pressure_Daily"
    )


# ============= EOF =============================================
