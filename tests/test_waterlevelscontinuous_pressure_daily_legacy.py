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
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError, ProgrammingError

from db.engine import session_ctx
from db.nma_legacy import NMA_WaterLevelsContinuous_Pressure_Daily


def _next_global_id() -> UUID:
    return uuid4()


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


# ===================== CREATE tests ==========================
def test_create_pressure_daily_all_fields(water_well_thing):
    """Test creating a pressure daily record with required fields."""
    with session_ctx() as session:
        now = datetime(2024, 1, 1, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            object_id=_next_object_id(),
            well_id=uuid4(),
            point_id=water_well_thing.name,
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
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == water_well_thing.name
        assert record.date_measured == now

        session.delete(record)
        session.commit()


def test_create_pressure_daily_minimal(water_well_thing):
    """Test creating a pressure daily record with minimal fields."""
    with session_ctx() as session:
        now = datetime(2024, 1, 2, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id=water_well_thing.name,
            date_measured=now,
            created=now,
            updated=now,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == water_well_thing.name

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_pressure_daily_by_global_id(water_well_thing):
    """Test reading a pressure daily record by GlobalID."""
    with session_ctx() as session:
        now = datetime(2024, 1, 3, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id=water_well_thing.name,
            date_measured=now,
            created=now,
            updated=now,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(
            NMA_WaterLevelsContinuous_Pressure_Daily, record.global_id
        )
        assert fetched is not None
        assert fetched.global_id == record.global_id
        assert fetched.point_id == water_well_thing.name

        session.delete(record)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_pressure_daily(water_well_thing):
    """Test updating a pressure daily record."""
    with session_ctx() as session:
        now = datetime(2024, 1, 4, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id=water_well_thing.name,
            date_measured=now,
            created=now,
            updated=now,
            thing_id=water_well_thing.id,
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
def test_delete_pressure_daily(water_well_thing):
    """Test deleting a pressure daily record."""
    with session_ctx() as session:
        now = datetime(2024, 1, 5, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id=water_well_thing.name,
            date_measured=now,
            created=now,
            updated=now,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(
            NMA_WaterLevelsContinuous_Pressure_Daily, record.global_id
        )
        assert fetched is None


# ===================== Column existence tests ==========================
def test_pressure_daily_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "global_id",
        "object_id",
        "well_id",
        "thing_id",
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
            NMA_WaterLevelsContinuous_Pressure_Daily, column
        ), f"Expected column '{column}' not found in pressure daily model"


def test_pressure_daily_table_name():
    """Test that the table name follows convention."""
    assert (
        NMA_WaterLevelsContinuous_Pressure_Daily.__tablename__
        == "NMA_WaterLevelsContinuous_Pressure_Daily"
    )


# ===================== Relational Integrity Tests ======================


def test_pressure_daily_thing_id_required():
    """
    VERIFIES: 'thing_id IS NOT NULL' and Foreign Key presence.
    Ensures the DB rejects records without a Thing linkage.
    """
    with session_ctx() as session:
        now = datetime(2024, 1, 6, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id="PD-1006",
            date_measured=now,
            created=now,
            updated=now,
        )
        session.add(record)

        with pytest.raises((IntegrityError, ProgrammingError)):
            session.flush()
        session.rollback()


def test_pressure_daily_invalid_thing_id_rejected(water_well_thing):
    """
    VERIFIES: foreign key integrity on thing_id.
    Ensures the DB rejects updates to a non-existent Thing.
    """
    with session_ctx() as session:
        now = datetime(2024, 1, 7, 12, 0, 0)
        record = NMA_WaterLevelsContinuous_Pressure_Daily(
            global_id=_next_global_id(),
            point_id=water_well_thing.name,
            date_measured=now,
            created=now,
            updated=now,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        with pytest.raises((IntegrityError, ProgrammingError)):
            record.thing_id = 999999
            session.flush()
        session.rollback()


# ============= EOF =============================================
