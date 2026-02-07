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
Unit tests for NMA_SurfaceWaterPhotos legacy model.

These tests verify the migration of columns from the legacy NMA_SurfaceWaterPhotos table.
Migrated columns:
- SurfaceID -> surface_id
- PointID -> point_id
- OLEPath -> ole_path
- OBJECTID -> object_id
- GlobalID -> global_id
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_SurfaceWaterData, NMA_SurfaceWaterPhotos
from db.thing import Thing


def _next_object_id() -> int:
    # Use a negative value to avoid collisions with existing legacy OBJECTIDs.
    return -(uuid4().int % 2_000_000_000)


def _attach_thing_with_location(session, water_well_thing):
    location_id = uuid4()
    thing = session.get(Thing, water_well_thing.id)
    thing.nma_pk_location = str(location_id)
    session.commit()
    return thing, location_id


def _create_surface_water_data(session, water_well_thing):
    thing, location_id = _attach_thing_with_location(session, water_well_thing)
    record = NMA_SurfaceWaterData(
        location_id=location_id,
        thing_id=thing.id,
        surface_id=uuid4(),
        point_id="SW-1000",
        object_id=_next_object_id(),
    )
    session.add(record)
    session.commit()
    return record


def test_create_surface_water_photos_all_fields(water_well_thing):
    """Test creating a surface water photos record with all fields."""
    with session_ctx() as session:
        parent = _create_surface_water_data(session, water_well_thing)
        record = NMA_SurfaceWaterPhotos(
            surface_id=parent.surface_id,
            point_id="SW-0001",
            ole_path="photo.jpg",
            object_id=123,
            global_id=uuid4(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.surface_id is not None
        assert record.point_id == "SW-0001"
        assert record.ole_path == "photo.jpg"
        assert record.object_id == 123

        session.delete(record)
        session.delete(parent)
        session.commit()


def test_create_surface_water_photos_minimal(water_well_thing):
    """Test creating a surface water photos record with required fields only."""
    with session_ctx() as session:
        parent = _create_surface_water_data(session, water_well_thing)
        record = NMA_SurfaceWaterPhotos(
            point_id="SW-0002",
            surface_id=parent.surface_id,
            global_id=uuid4(),
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.point_id == "SW-0002"
        assert record.surface_id is not None
        assert record.ole_path is None
        assert record.object_id is None

        session.delete(record)
        session.delete(parent)
        session.commit()


# ============= EOF =============================================
