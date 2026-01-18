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
Unit tests for WeatherData legacy model.

These tests verify the migration of columns from the legacy WeatherData table.
Migrated columns (excluding SSMA_TimeStamp):
- LocationId -> location_id
- PointID -> point_id
- WeatherID -> weather_id
- OBJECTID -> object_id
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import WeatherData


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


# ===================== CREATE tests ==========================
def test_create_weather_data_all_fields():
    """Test creating a weather data record with all migrated fields."""
    with session_ctx() as session:
        record = WeatherData(
            object_id=_next_object_id(),
            location_id=uuid4(),
            point_id="WX-1001",
            weather_id=uuid4(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.object_id is not None
        assert record.point_id == "WX-1001"
        assert record.location_id is not None
        assert record.weather_id is not None

        session.delete(record)
        session.commit()


def test_create_weather_data_minimal():
    """Test creating a weather data record with minimal fields."""
    with session_ctx() as session:
        record = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1002",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.object_id is not None
        assert record.point_id == "WX-1002"
        assert record.location_id is None
        assert record.weather_id is None

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_weather_data_by_object_id():
    """Test reading a specific weather data record by OBJECTID."""
    with session_ctx() as session:
        record = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1003",
        )
        session.add(record)
        session.commit()

        fetched = session.get(WeatherData, record.object_id)
        assert fetched is not None
        assert fetched.object_id == record.object_id
        assert fetched.point_id == "WX-1003"

        session.delete(record)
        session.commit()


def test_query_weather_data_by_point_id():
    """Test querying weather data by point_id."""
    with session_ctx() as session:
        record1 = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1004",
        )
        record2 = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1005",
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(WeatherData).filter(WeatherData.point_id == "WX-1004").all()
        )
        assert len(results) >= 1
        assert all(r.point_id == "WX-1004" for r in results)

        session.delete(record1)
        session.delete(record2)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_weather_data():
    """Test updating a weather data record."""
    with session_ctx() as session:
        record = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1006",
        )
        session.add(record)
        session.commit()

        new_location_id = uuid4()
        new_weather_id = uuid4()
        record.location_id = new_location_id
        record.weather_id = new_weather_id
        session.commit()
        session.refresh(record)

        assert record.location_id == new_location_id
        assert record.weather_id == new_weather_id

        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_weather_data():
    """Test deleting a weather data record."""
    with session_ctx() as session:
        record = WeatherData(
            object_id=_next_object_id(),
            point_id="WX-1007",
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(WeatherData, record.object_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_weather_data_has_all_migrated_columns():
    """
    Test that the model has all expected columns from WeatherData.
    """
    expected_columns = [
        "location_id",
        "point_id",
        "weather_id",
        "object_id",
    ]

    for column in expected_columns:
        assert hasattr(
            WeatherData, column
        ), f"Expected column '{column}' not found in WeatherData model"


def test_weather_data_table_name():
    """Test that the table name follows convention."""
    assert WeatherData.__tablename__ == "NMA_WeatherData"


# ============= EOF =============================================
