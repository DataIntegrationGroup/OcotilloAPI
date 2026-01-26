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
Unit tests for Soil_Rock_Results legacy model.

These tests verify the migration of columns from the legacy Soil_Rock_Results table.
Migrated columns:
- Point_ID -> point_id
- Sample Type -> sample_type
- Date Sampled -> date_sampled
- d13C -> d13c
- d18O -> d18o
- Sampled by -> sampled_by
- SSMA_TimeStamp -> ssma_timestamp
"""

from db.engine import session_ctx
from db.nma_legacy import NMA_Soil_Rock_Results


def test_create_soil_rock_results_all_fields(water_well_thing):
    """Test creating a soil/rock results record with all fields."""
    with session_ctx() as session:
        record = NMA_Soil_Rock_Results(
            point_id="SR-0001",
            sample_type="Soil",
            date_sampled="2026-01-01",
            d13c=-5.5,
            d18o=12.3,
            sampled_by="Tester",
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.point_id == "SR-0001"
        assert record.sample_type == "Soil"
        assert record.date_sampled == "2026-01-01"
        assert record.d13c == -5.5
        assert record.d18o == 12.3
        assert record.sampled_by == "Tester"
        assert record.thing_id == water_well_thing.id
        session.delete(record)
        session.commit()


def test_create_soil_rock_results_minimal():
    """Test creating a soil/rock results record with required fields only."""
    with session_ctx() as session:
        record = NMA_Soil_Rock_Results()
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.point_id is None
        assert record.sample_type is None
        assert record.date_sampled is None
        assert record.d13c is None
        assert record.d18o is None
        assert record.sampled_by is None
        session.delete(record)
        session.commit()


# ===================== FK Enforcement tests (Issue #363) ==========================


def test_soil_rock_results_validator_rejects_none_thing_id():
    """NMA_Soil_Rock_Results validator rejects None thing_id."""
    import pytest

    with pytest.raises(ValueError, match="requires a parent Thing"):
        NMA_Soil_Rock_Results(
            point_id="ORPHAN-TEST",
            thing_id=None,
        )


def test_soil_rock_results_thing_id_not_nullable():
    """NMA_Soil_Rock_Results.thing_id column is NOT NULL."""
    col = NMA_Soil_Rock_Results.__table__.c.thing_id
    assert col.nullable is False, "thing_id should be NOT NULL"


def test_soil_rock_results_fk_has_cascade():
    """NMA_Soil_Rock_Results.thing_id FK has ondelete=CASCADE."""
    col = NMA_Soil_Rock_Results.__table__.c.thing_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_soil_rock_results_back_populates_thing(water_well_thing):
    """NMA_Soil_Rock_Results.thing navigates back to Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_Soil_Rock_Results(
            point_id="BP-SOIL-01",
            thing_id=well.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.thing is not None
        assert record.thing.id == well.id

        session.delete(record)
        session.commit()


# ============= EOF =============================================
