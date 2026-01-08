# ===============================================================================
# Copyright 2025 ross
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
Unit tests for MinorTraceChemistry model.

These tests verify the migration of columns from NMAquifer MinorandTraceChemistry table.
Migrated columns (excluding GlobalID, OBJECTID, SSMA_TimeStamp, SamplePointID,
SamplePtID, WCLab_ID):
- AnalysesAgency -> analyses_agency
- Symbol -> symbol (detect flag indicator)
- SampleValue -> sample_value
- Units -> units
- Uncertainty -> uncertainty
- AnalysisMethod -> analysis_method
- AnalysisDate -> analysis_date
- Notes -> notes
- Volume -> volume
- VolumeUnit -> volume_unit
- Analyte -> analyte
"""
import pytest
from datetime import datetime, timezone

from db.engine import session_ctx
from db.minor_trace_chemistry import MinorTraceChemistry


# ===================== CREATE tests ==========================
def test_create_minor_trace_chemistry_all_fields():
    """Test creating a minor trace chemistry record with all migrated fields."""
    with session_ctx() as session:
        record = MinorTraceChemistry(
            analyses_agency="NMBGMR",
            analyte="As",
            symbol="<",
            sample_value=0.005,
            units="mg/L",
            uncertainty=0.001,
            analysis_method="ICP-MS",
            analysis_date=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            notes="Below detection limit",
            volume=100,
            volume_unit="mL",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.analyses_agency == "NMBGMR"
        assert record.analyte == "As"
        assert record.symbol == "<"
        assert record.sample_value == 0.005
        assert record.units == "mg/L"
        assert record.uncertainty == 0.001
        assert record.analysis_method == "ICP-MS"
        assert record.notes == "Below detection limit"
        assert record.volume == 100
        assert record.volume_unit == "mL"

        # Cleanup
        session.delete(record)
        session.commit()


def test_create_minor_trace_chemistry_minimal():
    """Test creating a minor trace chemistry record with minimal fields."""
    with session_ctx() as session:
        record = MinorTraceChemistry(
            analyte="U",
            sample_value=15.2,
            units="ug/L",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.analyte == "U"
        assert record.sample_value == 15.2
        assert record.units == "ug/L"
        # Nullable fields should be None
        assert record.analyses_agency is None
        assert record.symbol is None
        assert record.uncertainty is None
        assert record.analysis_method is None
        assert record.analysis_date is None
        assert record.notes is None
        assert record.volume is None
        assert record.volume_unit is None

        # Cleanup
        session.delete(record)
        session.commit()


def test_create_minor_trace_chemistry_null_sample_value():
    """Test creating a record where sample_value is null (non-detect scenario)."""
    with session_ctx() as session:
        record = MinorTraceChemistry(
            analyte="Fe",
            symbol="<",
            sample_value=None,
            units="mg/L",
            notes="Non-detect",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None
        assert record.sample_value is None
        assert record.symbol == "<"

        # Cleanup
        session.delete(record)
        session.commit()


# ===================== READ tests ==========================
def test_read_minor_trace_chemistry_by_id():
    """Test reading a specific minor trace chemistry record by ID."""
    with session_ctx() as session:
        # Create a record
        record = MinorTraceChemistry(
            analyte="Mn",
            sample_value=0.05,
            units="mg/L",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        created_id = record.id

        # Read it back
        fetched = session.get(MinorTraceChemistry, created_id)
        assert fetched is not None
        assert fetched.id == created_id
        assert fetched.analyte == "Mn"
        assert fetched.sample_value == 0.05
        assert fetched.units == "mg/L"

        # Cleanup
        session.delete(record)
        session.commit()


def test_query_minor_trace_chemistry_by_analyte():
    """Test querying records by analyte."""
    with session_ctx() as session:
        # Create test records
        record1 = MinorTraceChemistry(
            analyte="Se",
            sample_value=0.01,
            units="mg/L",
            release_status="draft",
        )
        record2 = MinorTraceChemistry(
            analyte="Ba",
            sample_value=0.5,
            units="mg/L",
            release_status="draft",
        )
        session.add_all([record1, record2])
        session.commit()

        # Query by analyte
        results = (
            session.query(MinorTraceChemistry)
            .filter(MinorTraceChemistry.analyte == "Se")
            .all()
        )
        assert len(results) >= 1
        assert all(r.analyte == "Se" for r in results)

        # Cleanup
        session.delete(record1)
        session.delete(record2)
        session.commit()


def test_query_minor_trace_chemistry_by_agency():
    """Test querying records by analyses_agency."""
    with session_ctx() as session:
        record = MinorTraceChemistry(
            analyte="Mo",
            sample_value=0.02,
            units="mg/L",
            analyses_agency="NMBGMR",
            release_status="draft",
        )
        session.add(record)
        session.commit()

        # Query by agency
        results = (
            session.query(MinorTraceChemistry)
            .filter(MinorTraceChemistry.analyses_agency == "NMBGMR")
            .all()
        )
        assert len(results) >= 1
        assert all(r.analyses_agency == "NMBGMR" for r in results)

        # Cleanup
        session.delete(record)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_minor_trace_chemistry():
    """Test updating a minor trace chemistry record."""
    with session_ctx() as session:
        # Create a record
        record = MinorTraceChemistry(
            analyte="Pb",
            sample_value=0.01,
            units="mg/L",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        created_id = record.id

        # Update the record
        record.sample_value = 0.015
        record.notes = "Updated value after reanalysis"
        session.commit()
        session.refresh(record)

        assert record.sample_value == 0.015
        assert record.notes == "Updated value after reanalysis"
        # Original values should be preserved
        assert record.analyte == "Pb"
        assert record.units == "mg/L"

        # Cleanup
        session.delete(record)
        session.commit()


def test_update_minor_trace_chemistry_all_fields():
    """Test updating all migrated fields."""
    with session_ctx() as session:
        # Create a record
        record = MinorTraceChemistry(
            analyte="Zn",
            sample_value=0.1,
            units="mg/L",
            release_status="draft",
        )
        session.add(record)
        session.commit()

        # Update all fields
        record.analyses_agency = "USGS"
        record.symbol = ">"
        record.sample_value = 0.2
        record.units = "ug/L"
        record.uncertainty = 0.02
        record.analysis_method = "ICP-OES"
        record.analysis_date = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        record.notes = "Reanalyzed sample"
        record.volume = 50
        record.volume_unit = "mL"
        session.commit()
        session.refresh(record)

        assert record.analyses_agency == "USGS"
        assert record.symbol == ">"
        assert record.sample_value == 0.2
        assert record.units == "ug/L"
        assert record.uncertainty == 0.02
        assert record.analysis_method == "ICP-OES"
        assert record.notes == "Reanalyzed sample"
        assert record.volume == 50
        assert record.volume_unit == "mL"

        # Cleanup
        session.delete(record)
        session.commit()


# ===================== DELETE tests ==========================
def test_delete_minor_trace_chemistry():
    """Test deleting a minor trace chemistry record."""
    with session_ctx() as session:
        # Create a record
        record = MinorTraceChemistry(
            analyte="Cd",
            sample_value=0.001,
            units="mg/L",
            release_status="draft",
        )
        session.add(record)
        session.commit()
        created_id = record.id

        # Delete the record
        session.delete(record)
        session.commit()

        # Verify it's gone
        fetched = session.get(MinorTraceChemistry, created_id)
        assert fetched is None


# ===================== Column existence tests ==========================
def test_minor_trace_chemistry_has_all_migrated_columns():
    """
    Test that the model has all expected columns from NMAquifer migration.

    Expected columns (from MinorandTraceChemistry, excluding GlobalID, OBJECTID,
    SSMA_TimeStamp, SamplePointID, SamplePtID, WCLab_ID):
    - analyses_agency (from AnalysesAgency)
    - analyte (from Analyte)
    - symbol (from Symbol)
    - sample_value (from SampleValue)
    - units (from Units)
    - uncertainty (from Uncertainty)
    - analysis_method (from AnalysisMethod)
    - analysis_date (from AnalysisDate)
    - notes (from Notes)
    - volume (from Volume)
    - volume_unit (from VolumeUnit)
    """
    # Verify the model class has all expected attributes
    expected_columns = [
        "analyses_agency",
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
    ]

    for column in expected_columns:
        assert hasattr(
            MinorTraceChemistry, column
        ), f"Expected column '{column}' not found in MinorTraceChemistry model"


def test_minor_trace_chemistry_table_name():
    """Test that the table name follows convention."""
    assert MinorTraceChemistry.__tablename__ == "minor_trace_chemistry"


# ============= EOF =============================================
