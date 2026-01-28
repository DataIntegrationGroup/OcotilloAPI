# ===============================================================================
# Copyright 2026
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
Unit tests for NMA_Stratigraphy (lithology log) legacy model.

These tests verify FK enforcement for Issue #363.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy UUID (UNIQUE)
- nma_well_id: Legacy WellID UUID
- nma_point_id: Legacy PointID string
- nma_object_id: Legacy OBJECTID (UNIQUE)
"""

from uuid import uuid4

import pytest

from db.engine import session_ctx
from db.nma_legacy import NMA_Stratigraphy


def _next_global_id():
    return uuid4()


# ===================== CREATE tests ==========================


def test_create_stratigraphy_with_thing(water_well_thing):
    """Test creating a stratigraphy record with a parent Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_Stratigraphy(
            nma_global_id=_next_global_id(),
            nma_point_id="STRAT-01",
            thing_id=well.id,
            strat_top=0,
            strat_bottom=10,
            lithology="Sand",  # Max 4 chars
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.nma_point_id == "STRAT-01"
        assert record.thing_id == well.id

        session.delete(record)
        session.commit()


# ===================== FK Enforcement tests (Issue #363) ==========================


def test_stratigraphy_validator_rejects_none_thing_id():
    """NMA_Stratigraphy validator rejects None thing_id."""
    with pytest.raises(ValueError, match="requires a parent Thing"):
        NMA_Stratigraphy(
            nma_global_id=_next_global_id(),
            nma_point_id="ORPHAN-STRAT",
            thing_id=None,
        )


def test_stratigraphy_thing_id_not_nullable():
    """NMA_Stratigraphy.thing_id column is NOT NULL."""
    col = NMA_Stratigraphy.__table__.c.thing_id
    assert col.nullable is False, "thing_id should be NOT NULL"


def test_stratigraphy_fk_has_cascade():
    """NMA_Stratigraphy.thing_id FK has ondelete=CASCADE."""
    col = NMA_Stratigraphy.__table__.c.thing_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_stratigraphy_back_populates_thing(water_well_thing):
    """NMA_Stratigraphy.thing navigates back to Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)
        record = NMA_Stratigraphy(
            nma_global_id=_next_global_id(),
            nma_point_id="BPSTRAT01",  # Max 10 chars
            thing_id=well.id,
            strat_top=0,
            strat_bottom=10,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.thing is not None
        assert record.thing.id == well.id

        session.delete(record)
        session.commit()


# ===================== Integer PK tests ==========================


def test_stratigraphy_has_integer_pk():
    """NMA_Stratigraphy.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_Stratigraphy.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_stratigraphy_nma_global_id_is_unique():
    """NMA_Stratigraphy.nma_global_id is UNIQUE."""
    # Use database column name (nma_GlobalID), not Python attribute name
    col = NMA_Stratigraphy.__table__.c["nma_GlobalID"]
    assert col.unique is True


# ============= EOF =============================================
