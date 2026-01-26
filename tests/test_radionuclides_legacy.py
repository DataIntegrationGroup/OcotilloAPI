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
Migrated columns (excluding SSMA_TimeStamp):
- SamplePtID -> sample_pt_id
- SamplePointID -> sample_point_id
- Analyte -> analyte
- Symbol -> symbol
- SampleValue -> sample_value
- Units -> units
- Uncertainty -> uncertainty
- AnalysisMethod -> analysis_method
- AnalysisDate -> analysis_date
- Notes -> notes
- Volume -> volume
- VolumeUnit -> volume_unit
- OBJECTID -> object_id
- GlobalID -> global_id
- AnalysesAgency -> analyses_agency
- WCLab_ID -> wclab_id
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
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
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
            wclab_id="LAB-001",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.sample_pt_id == sample_info.sample_pt_id
        assert record.sample_point_id == sample_info.sample_point_id
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
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.sample_pt_id == sample_info.sample_pt_id
        assert record.analyte is None
        assert record.units is None

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== READ tests ==========================
def test_read_radionuclides_by_global_id(water_well_thing):
    """Test reading a radionuclides record by GlobalID."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_Radionuclides, record.global_id)
        assert fetched is not None
        assert fetched.global_id == record.global_id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_query_radionuclides_by_sample_point_id(water_well_thing):
    """Test querying radionuclides by sample_point_id."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record1 = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
        )
        record2 = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id="OTHER-PT",
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(NMA_Radionuclides)
            .filter(NMA_Radionuclides.sample_point_id == sample_info.sample_point_id)
            .all()
        )
        assert len(results) >= 1
        assert all(r.sample_point_id == sample_info.sample_point_id for r in results)

        session.delete(record1)
        session.delete(record2)
        session.delete(sample_info)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_radionuclides(water_well_thing):
    """Test updating a radionuclides record."""
    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
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
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            thing_id=water_well_thing.id,
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(NMA_Radionuclides, record.global_id)
        assert fetched is None

        session.delete(sample_info)
        session.commit()


# ===================== Column existence tests ==========================
def test_radionuclides_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "thing_id",
        "sample_pt_id",
        "sample_point_id",
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
        "object_id",
        "global_id",
        "analyses_agency",
        "wclab_id",
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
    """NMA_Radionuclides.thing_id FK has ondelete=CASCADE."""
    col = NMA_Radionuclides.__table__.c.thing_id
    fk = list(col.foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_radionuclides_back_populates_thing(water_well_thing):
    """NMA_Radionuclides.thing navigates back to Thing."""
    with session_ctx() as session:
        well = session.merge(water_well_thing)

        # Radionuclides requires a chemistry_sample_info
        sample_info = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=well.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMA_Radionuclides(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            thing_id=well.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.thing is not None
        assert record.thing.id == well.id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ============= EOF =============================================
