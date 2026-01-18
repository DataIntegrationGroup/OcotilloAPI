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
Unit tests for AssociatedData legacy model.

These tests verify the migration of columns from the legacy AssociatedData table.
Migrated columns:
- LocationId -> location_id
- PointID -> point_id
- AssocID -> assoc_id
- Notes -> notes
- Formation -> formation
- OBJECTID -> object_id
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import AssociatedData


def test_create_associated_data_all_fields(water_well_thing):
    """Test creating an associated data record with all fields."""
    with session_ctx() as session:
        record = AssociatedData(
            location_id=uuid4(),
            point_id="AA-0001",
            assoc_id=uuid4(),
            notes="Legacy notes",
            formation="TEST",
            object_id=42,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.assoc_id is not None
        assert record.location_id is not None
        assert record.point_id == "AA-0001"
        assert record.notes == "Legacy notes"
        assert record.formation == "TEST"
        assert record.object_id == 42
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


def test_create_associated_data_minimal():
    """Test creating an associated data record with required fields only."""
    with session_ctx() as session:
        record = AssociatedData(assoc_id=uuid4())
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.assoc_id is not None
        assert record.location_id is None
        assert record.point_id is None
        assert record.notes is None
        assert record.formation is None
        assert record.object_id is None

        session.delete(record)
        session.commit()


# ============= EOF =============================================
