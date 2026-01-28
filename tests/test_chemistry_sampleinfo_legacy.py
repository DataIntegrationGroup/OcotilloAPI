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
Unit tests for NMA_Chemistry_SampleInfo legacy model.

These tests verify the migration of columns from the legacy Chemistry_SampleInfo table.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_sample_pt_id: Legacy SamplePtID UUID (UNIQUE)
- nma_sample_point_id: Legacy SamplePointID string
- nma_wclab_id: Legacy WCLab_ID string
- nma_location_id: Legacy LocationId UUID
- nma_object_id: Legacy OBJECTID (UNIQUE)
"""

from datetime import datetime
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import NMA_Chemistry_SampleInfo


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


def _next_sample_pt_id():
    return uuid4()


# ===================== CREATE tests ==========================
def test_create_chemistry_sampleinfo_all_fields(water_well_thing):
    """Test creating a chemistry sample info record with all fields."""
    with session_ctx() as session:
        record = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
            nma_wclab_id="LAB-123",
            collection_date=datetime(2024, 1, 1, 10, 30, 0),
            collection_method="Grab",
            collected_by="Tech",
            analyses_agency="Agency A",
            sample_type="Water",
            sample_material_not_h2o="Yes",
            water_type="Fresh",
            study_sample="Yes",
            data_source="SRC",
            data_quality=True,
            public_release=True,
            added_day_to_date=False,
            added_month_day_to_date=False,
            sample_notes="Notes",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_sample_pt_id is not None
        assert record.nma_sample_point_id is not None
        assert record.nma_wclab_id == "LAB-123"
        assert record.collection_date == datetime(2024, 1, 1, 10, 30, 0)
        assert record.sample_material_not_h2o == "Yes"
        assert record.study_sample == "Yes"

        session.delete(record)
        session.commit()


def test_create_chemistry_sampleinfo_minimal(water_well_thing):
    """Test creating a chemistry sample info record with minimal fields."""
    with session_ctx() as session:
        record = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_sample_pt_id is not None
        assert record.nma_sample_point_id is not None
        assert record.collection_date is None

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_chemistry_sampleinfo_by_id(water_well_thing):
    """Test reading a chemistry sample info record by Integer ID."""
    with session_ctx() as session:
        record = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_Chemistry_SampleInfo, record.id)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.nma_sample_pt_id == record.nma_sample_pt_id
        assert fetched.nma_sample_point_id == record.nma_sample_point_id

        session.delete(record)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_chemistry_sampleinfo(water_well_thing):
    """Test updating a chemistry sample info record."""
    with session_ctx() as session:
        record = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        record.sample_notes = "Updated notes"
        record.public_release = False
        session.commit()
        session.refresh(record)

        assert record.sample_notes == "Updated notes"
        assert record.public_release is False

        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_chemistry_sampleinfo(water_well_thing):
    """Test deleting a chemistry sample info record."""
    with session_ctx() as session:
        record = NMA_Chemistry_SampleInfo(
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        record_id = record.id

        session.delete(record)
        session.commit()

        fetched = session.get(NMA_Chemistry_SampleInfo, record_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_chemistry_sampleinfo_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "id",
        "nma_sample_point_id",
        "nma_sample_pt_id",
        "nma_wclab_id",
        "thing_id",
        "collection_date",
        "collection_method",
        "collected_by",
        "analyses_agency",
        "sample_type",
        "sample_material_not_h2o",
        "water_type",
        "study_sample",
        "data_source",
        "data_quality",
        "public_release",
        "added_day_to_date",
        "added_month_day_to_date",
        "sample_notes",
        "nma_object_id",
        "nma_location_id",
    ]

    for column in expected_columns:
        assert hasattr(
            NMA_Chemistry_SampleInfo, column
        ), f"Expected column '{column}' not found in NMA_Chemistry_SampleInfo model"


def test_chemistry_sampleinfo_table_name():
    """Test that the table name follows convention."""
    assert NMA_Chemistry_SampleInfo.__tablename__ == "NMA_Chemistry_SampleInfo"


# ===================== Integer PK tests ==========================


def test_chemistry_sampleinfo_has_integer_pk():
    """NMA_Chemistry_SampleInfo.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_Chemistry_SampleInfo.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_chemistry_sampleinfo_nma_sample_pt_id_is_unique():
    """NMA_Chemistry_SampleInfo.nma_sample_pt_id is UNIQUE."""
    # Use database column name (nma_SamplePtID), not Python attribute name
    col = NMA_Chemistry_SampleInfo.__table__.c["nma_SamplePtID"]
    assert col.unique is True


# ============= EOF =============================================
