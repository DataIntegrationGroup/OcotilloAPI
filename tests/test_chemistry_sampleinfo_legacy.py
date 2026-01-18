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
Unit tests for ChemistrySampleInfo legacy model.

These tests verify the migration of columns from the legacy Chemistry_SampleInfo table.
Migrated columns:
- OBJECTID -> object_id
- SamplePointID -> sample_point_id
- SamplePtID -> sample_pt_id
- WCLab_ID -> wclab_id
- CollectionDate -> collection_date
- CollectionMethod -> collection_method
- CollectedBy -> collected_by
- AnalysesAgency -> analyses_agency
- SampleType -> sample_type
- SampleMaterialNotH2O -> sample_material_not_h2o
- WaterType -> water_type
- StudySample -> study_sample
- DataSource -> data_source
- DataQuality -> data_quality
- PublicRelease -> public_release
- AddedDaytoDate -> added_day_to_date
- AddedMonthDaytoDate -> added_month_day_to_date
- SampleNotes -> sample_notes
"""

from datetime import datetime
from uuid import uuid4

from db.engine import session_ctx
from db.nma_legacy import ChemistrySampleInfo


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


def _next_sample_pt_id():
    return uuid4()


# ===================== CREATE tests ==========================
def test_create_chemistry_sampleinfo_all_fields(water_well_thing):
    """Test creating a chemistry sample info record with all fields."""
    with session_ctx() as session:
        record = ChemistrySampleInfo(
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
            wclab_id="LAB-123",
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

        assert record.sample_pt_id is not None
        assert record.sample_point_id is not None
        assert record.wclab_id == "LAB-123"
        assert record.collection_date == datetime(2024, 1, 1, 10, 30, 0)
        assert record.sample_material_not_h2o == "Yes"
        assert record.study_sample == "Yes"

        session.delete(record)
        session.commit()


def test_create_chemistry_sampleinfo_minimal(water_well_thing):
    """Test creating a chemistry sample info record with minimal fields."""
    with session_ctx() as session:
        record = ChemistrySampleInfo(
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.sample_pt_id is not None
        assert record.sample_point_id is not None
        assert record.collection_date is None

        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_chemistry_sampleinfo_by_object_id(water_well_thing):
    """Test reading a chemistry sample info record by OBJECTID."""
    with session_ctx() as session:
        record = ChemistrySampleInfo(
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(ChemistrySampleInfo, record.sample_pt_id)
        assert fetched is not None
        assert fetched.sample_pt_id == record.sample_pt_id
        assert fetched.sample_point_id == record.sample_point_id

        session.delete(record)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_chemistry_sampleinfo(water_well_thing):
    """Test updating a chemistry sample info record."""
    with session_ctx() as session:
        record = ChemistrySampleInfo(
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
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
        record = ChemistrySampleInfo(
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing_id=water_well_thing.id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(ChemistrySampleInfo, record.sample_pt_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_chemistry_sampleinfo_has_all_migrated_columns():
    """Test that the model has all expected columns."""
    expected_columns = [
        "sample_point_id",
        "sample_pt_id",
        "wclab_id",
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
        "object_id",
        "location_id",
    ]

    for column in expected_columns:
        assert hasattr(
            ChemistrySampleInfo, column
        ), f"Expected column '{column}' not found in ChemistrySampleInfo model"


def test_chemistry_sampleinfo_table_name():
    """Test that the table name follows convention."""
    assert ChemistrySampleInfo.__tablename__ == "NMA_Chemistry_SampleInfo"


# ============= EOF =============================================
