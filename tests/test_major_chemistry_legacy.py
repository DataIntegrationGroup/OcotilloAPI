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
Unit tests for MajorChemistry legacy model.

These tests verify the migration of columns from the legacy MajorChemistry table.
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
from db.nma_legacy import ChemistrySampleInfo, NMAMajorChemistry


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


# ===================== CREATE tests ==========================
def test_create_major_chemistry_all_fields(water_well_thing):
    """Test creating a major chemistry record with all fields."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMAMajorChemistry(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
            analyte="Ca",
            symbol="<",
            sample_value=12.3,
            units="mg/L",
            uncertainty=0.1,
            analysis_method="ICP-MS",
            analysis_date=datetime(2024, 6, 15, 0, 0, 0),
            notes="Test notes",
            volume=250,
            volume_unit="mL",
            analyses_agency="NMBGMR",
            wclab_id="LAB-101",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.sample_pt_id == sample_info.sample_pt_id
        assert record.sample_point_id == sample_info.sample_point_id
        assert record.analyte == "Ca"
        assert record.sample_value == 12.3
        assert record.uncertainty == 0.1

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_create_major_chemistry_minimal(water_well_thing):
    """Test creating a major chemistry record with minimal fields."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMAMajorChemistry(
            global_id=uuid4(),
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
def test_read_major_chemistry_by_global_id(water_well_thing):
    """Test reading a major chemistry record by GlobalID."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMAMajorChemistry(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMAMajorChemistry, record.global_id)
        assert fetched is not None
        assert fetched.global_id == record.global_id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_query_major_chemistry_by_sample_point_id(water_well_thing):
    """Test querying major chemistry by sample_point_id."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record1 = NMAMajorChemistry(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
        )
        record2 = NMAMajorChemistry(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id="OTHER-PT",
        )
        session.add_all([record1, record2])
        session.commit()

        results = (
            session.query(NMAMajorChemistry)
            .filter(NMAMajorChemistry.sample_point_id == sample_info.sample_point_id)
            .all()
        )
        assert len(results) >= 1
        assert all(r.sample_point_id == sample_info.sample_point_id for r in results)

        session.delete(record1)
        session.delete(record2)
        session.delete(sample_info)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_major_chemistry(water_well_thing):
    """Test updating a major chemistry record."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMAMajorChemistry(
            global_id=uuid4(),
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
def test_delete_major_chemistry(water_well_thing):
    """Test deleting a major chemistry record."""
    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            sample_pt_id=uuid4(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(sample_info)
        session.commit()

        record = NMAMajorChemistry(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(NMAMajorChemistry, record.global_id)
        assert fetched is None

        session.delete(sample_info)
        session.commit()


# ===================== Column existence tests ==========================
def test_major_chemistry_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "global_id",
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
        "analyses_agency",
        "wclab_id",
    ]

    for column in expected_columns:
        assert hasattr(
            NMAMajorChemistry, column
        ), f"Expected column '{column}' not found in NMAMajorChemistry model"


def test_major_chemistry_table_name():
    """Test that the table name follows convention."""
    assert NMAMajorChemistry.__tablename__ == "NMA_MajorChemistry"


# ============= EOF =============================================
