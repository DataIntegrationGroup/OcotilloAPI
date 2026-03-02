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
Unit tests for Radionuclides legacy model.

These tests verify the migration of columns from the legacy Radionuclides table.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy GlobalID UUID (UNIQUE)
- chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
- nma_sample_pt_id: Legacy SamplePtID UUID (for audit)
- nma_sample_point_id: Legacy SamplePointID string
- nma_object_id: Legacy OBJECTID (UNIQUE)
- nma_wclab_id: Legacy WCLab_ID string
"""

from datetime import datetime
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_Radionuclides


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


# ===================== CREATE tests ==========================
def test_create_radionuclides_all_fields(water_well_thing):
    """Test creating a radionuclides record with all fields."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_pt_id=sample_info.nma_sample_pt_id,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="U-238",
            symbol="<",
            sample_value=0.12,
            units="pCi/L",
            uncertainty=0.01,
            analysis_method="ICP-MS",
            analysis_date=datetime(2024, 6, 15, 0, 0, 0),
            notes="Test notes",
            volume=250,
            volume_unit="mL",
            analyses_agency="NMBGMR",
            nma_wclab_id="LAB-001",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.chemistry_sample_info_id == sample_info.id
        assert record.nma_sample_pt_id == sample_info.nma_sample_pt_id
        assert record.nma_sample_point_id == sample_info.nma_sample_point_id
        assert record.analyte == "U-238"
        assert record.sample_value == 0.12
        assert record.uncertainty == 0.01

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_create_radionuclides_minimal(water_well_thing):
    """Test creating a radionuclides record with minimal fields."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.chemistry_sample_info_id == sample_info.id
        assert record.analyte is None
        assert record.units is None

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== READ tests ==========================
def test_read_radionuclides_by_id(water_well_thing):
    """Test reading a radionuclides record by Integer ID."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_Radionuclides, record.id)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.nma_global_id == record.nma_global_id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_query_radionuclides_by_nma_sample_point_id(water_well_thing):
    """Test querying radionuclides by nma_sample_point_id."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record1 = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_point_id=sample_info.nma_sample_point_id,
        )
        record2 = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_point_id="OTHER-PT",
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(NMA_Radionuclides)
            .filter(
                NMA_Radionuclides.nma_sample_point_id == sample_info.nma_sample_point_id
            )
            .all()
        )
        assert len(results) >= 1
        assert all(
            r.nma_sample_point_id == sample_info.nma_sample_point_id for r in results
        )

        session.delete(record1)
        session.delete(record2)
        session.delete(sample_info)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_radionuclides(water_well_thing):
    """Test updating a radionuclides record."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()

        record.analyses_agency = "Updated Agency"
        record.notes = "Updated notes"
        session.commit()
        session.refresh(record)

        assert record.analyses_agency == "Updated Agency"
        assert record.notes == "Updated notes"

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_radionuclides(water_well_thing):
    """Test deleting a radionuclides record."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()
        record_id = record.id

        session.delete(record)
        session.commit()

        fetched = session.get(NMA_Radionuclides, record_id)
        assert fetched is None

        session.delete(sample_info)
        session.commit()


# ===================== Column existence tests ==========================
def test_radionuclides_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "analyte",
        "symbol",
        "sample_value",
        "units",
        "uncertainty",
        "analysis_method",
        "analysis_date",
        "notes",
        "volume",
        "volume_unit",
        "nma_object_id",
        "analyses_agency",
        "nma_wclab_id",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_Radionuclides, column
        ), f"Expected column '{column}' not found in NMA_Radionuclides model"


def test_radionuclides_table_name():
    """Test that the table name follows convention."""
    assert NMA_Radionuclides.__tablename__ == "NMA_Radionuclides"


# ===================== FK Enforcement tests (Issue #363) ==========================


def test_radionuclides_fk_has_cascade():
    """NMA_Radionuclides.chemistry_sample_info_id FK has ondelete=CASCADE."""
    col = NMA_Radionuclides.__table__.c.chemistry_sample_info_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_radionuclides_back_populates_sample_info(water_well_thing):
    """NMA_Radionuclides <-> NMA_Chemistry_SampleInfo back_populates works."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=uuid4(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        record = NMA_Radionuclides(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.chemistry_sample_info is not None
        assert record.chemistry_sample_info.id == sample_info.id
        assert record in sample_info.radionuclides

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== Integer PK tests ==========================


def test_radionuclides_has_integer_pk():
    """NMA_Radionuclides.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_Radionuclides.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_radionuclides_nma_global_id_is_unique():
    """NMA_Radionuclides.nma_global_id is UNIQUE."""
    # Use database column name (nma_GlobalID), not Python attribute name
    col = NMA_Radionuclides.__table__.c["nma_GlobalID"]
    assert col.unique is True


def test_radionuclides_chemistry_sample_info_fk():
    """NMA_Radionuclides.chemistry_sample_info_id is Integer FK."""
    col = NMA_Radionuclides.__table__.c.chemistry_sample_info_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert "NMA_Chemistry_SampleInfo.id" in str(fks[0].target_fullname)


# ============= EOF =============================================
