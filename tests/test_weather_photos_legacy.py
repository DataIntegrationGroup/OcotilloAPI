# ==============================================================================
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
# ==============================================================================
"""
Unit tests for NMA_WeatherPhotos legacy model.

These tests verify the migration of columns from the legacy NMA_WeatherPhotos table.
Migrated columns:
- WeatherID -> weather_id
- PointID -> point_id
- OLEPath -> ole_path
- OBJECTID -> object_id
- GlobalID -> global_id
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_WeatherPhotos


def test_create_weather_photos_all_fields():
    """Test creating a weather photos record with all fields."""
    with session_ctx() as session:
        record = NMA_WeatherPhotos(
            weather_id=uuid4(),
            point_id="WP-0001",
            ole_path="weather.jpg",
            object_id=321,
            global_id=uuid4(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.weather_id is not None
        assert record.point_id == "WP-0001"
        assert record.ole_path == "weather.jpg"
        assert record.object_id == 321

        session.delete(record)
        session.commit()


def test_create_weather_photos_minimal():
    """Test creating a weather photos record with required fields only."""
    with session_ctx() as session:
        record = NMA_WeatherPhotos(
            point_id="WP-0002",
            global_id=uuid4(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == "WP-0002"
        assert record.weather_id is None
        assert record.ole_path is None
        assert record.object_id is None

        session.delete(record)
        session.commit()


# ============= EOF =============================================
