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
Unit tests for NMA_AssociatedData legacy model.

These tests verify the migration of columns from the legacy NMA_AssociatedData table.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_assoc_id: Legacy AssocID UUID (UNIQUE)
- nma_location_id: Legacy LocationId UUID (UNIQUE)
- nma_point_id: Legacy PointID string
- nma_object_id: Legacy OBJECTID (UNIQUE)
"""

from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_AssociatedData


def test_create_associated_data_all_fields(water_well_thing):
    """Test creating an associated data record with all fields."""
    with session_ctx() as session:
        record = NMA_AssociatedData(
            nma_location_id=uuid4(),
            nma_point_id="AA-0001",
            nma_assoc_id=uuid4(),
            notes="Legacy notes",
            formation="TEST",
            nma_object_id=42,
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_assoc_id is not None
        assert record.nma_location_id is not None
        assert record.nma_point_id == "AA-0001"
        assert record.notes == "Legacy notes"
        assert record.formation == "TEST"
        assert record.nma_object_id == 42
        assert record.thing_id == water_well_thing.id

        session.delete(record)
        session.commit()


def test_create_associated_data_minimal(water_well_thing):
    """Test creating an associated data record with required fields only."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_AssociatedData(nma_assoc_id=uuid4(), thing_id=well.id)
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_assoc_id is not None
        assert record.thing_id == well.id
        assert record.nma_location_id is None
        assert record.nma_point_id is None
        assert record.notes is None
        assert record.formation is None
        assert record.nma_object_id is None

        session.delete(record)
        session.commit()


# ===================== FK Enforcement tests (Issue #363) ==========================


def test_associated_data_validator_rejects_none_thing_id():
    """NMA_AssociatedData validator rejects None thing_id."""
    import pytest

    with pytest.raises(ValueError, match="requires a parent Thing"):
        NMA_AssociatedData(
            nma_assoc_id=uuid4(),
            nma_point_id="ORPHAN-TEST",
            thing_id=None,
        )


def test_associated_data_thing_id_not_nullable():
    """NMA_AssociatedData.thing_id column is NOT NULL."""
    col = NMA_AssociatedData.__table__.c.thing_id
    assert col.nullable is False, "thing_id should be NOT NULL"


def test_associated_data_fk_has_cascade():
    """NMA_AssociatedData.thing_id FK has ondelete=CASCADE."""
    col = NMA_AssociatedData.__table__.c.thing_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_associated_data_back_populates_thing(water_well_thing):
    """NMA_AssociatedData.thing navigates back to Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_AssociatedData(
            nma_assoc_id=uuid4(),
            nma_point_id="BPASSOC01",  # Max 10 chars
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


def test_associated_data_has_integer_pk():
    """NMA_AssociatedData.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_AssociatedData.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_associated_data_nma_assoc_id_is_unique():
    """NMA_AssociatedData.nma_assoc_id is UNIQUE."""
    col = NMA_AssociatedData.__table__.c.nma_assoc_id
    assert col.unique is True


# ============= EOF =============================================
