"""
Unit tests for FieldParameters legacy model.

These tests verify the migration of columns from the legacy FieldParameters table.
Migrated columns (excluding SSMA_TimeStamp):
- SamplePtID -> sample_pt_id
- SamplePointID -> sample_point_id
- FieldParameter -> field_parameter
- SampleValue -> sample_value
- Units -> units
- Notes -> notes
- OBJECTID -> object_id
- GlobalID -> global_id
- AnalysesAgency -> analyses_agency
- WCLab_ID -> wc_lab_id
"""

from uuid import uuid4

import pytest
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError, ProgrammingError

from db.engine import session_ctx
from db.nma_legacy import ChemistrySampleInfo, NMAFieldParameters


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


def _create_sample_info(session, water_well_thing) -> ChemistrySampleInfo:
    sample = ChemistrySampleInfo(
        sample_pt_id=uuid4(),
        sample_point_id=_next_sample_point_id(),
        thing_id=water_well_thing.id,
    )
    session.add(sample)
    session.commit()
    return sample


# ===================== Table and Column Existence Tests ==========================


def test_field_parameters_has_all_migrated_columns():
    """
    VERIFIES: The SQLAlchemy model matches the migration mapping contract.
    This ensures all Python-side attribute names exist as expected in the ORM.
    """
    mapper = inspect(NMAFieldParameters)
    actual_columns = [column.key for column in mapper.attrs]

    expected_columns = [
        "global_id",
        "sample_pt_id",
        "sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "object_id",
        "analyses_agency",
        "wc_lab_id",
    ]

    for column in expected_columns:
        assert column in actual_columns, f"Model is missing expected column: {column}"


def test_field_parameters_table_name():
    """Test that the table name follows convention."""
    assert NMAFieldParameters.__tablename__ == "NMA_FieldParameters"


# ===================== Functional & CRUD Tests =========================


def test_field_parameters_persistence(water_well_thing):
    """
    Verifies that data correctly persists and retrieves for the core columns.
    This confirms the Postgres data types (REAL, UUID, VARCHAR) are compatible.
    """
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        test_global_id = uuid4()
        new_fp = NMAFieldParameters(
            global_id=test_global_id,
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id="PT-123",
            field_parameter="pH",
            sample_value=7.4,
            units="SU",
            notes="Legacy migration verification",
            analyses_agency="NMA Agency",
            wc_lab_id="WCLAB-01",
        )

        session.add(new_fp)
        session.commit()
        session.expire_all()

        retrieved = session.get(NMAFieldParameters, test_global_id)
        assert retrieved.sample_value == 7.4
        assert retrieved.field_parameter == "pH"
        assert retrieved.units == "SU"
        assert retrieved.analyses_agency == "NMA Agency"

        session.delete(new_fp)
        session.delete(sample_info)
        session.commit()


def test_object_id_auto_generation(water_well_thing):
    """Verifies that the OBJECTID (Identity) column auto-increments in Postgres."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        fp1 = NMAFieldParameters(
            sample_pt_id=sample_info.sample_pt_id,
            field_parameter="Temp",
        )
        session.add(fp1)
        session.commit()
        session.refresh(fp1)

        assert fp1.object_id is not None

        session.delete(fp1)
        session.delete(sample_info)
        session.commit()


# ===================== CREATE tests ==========================
def test_create_field_parameters_all_fields(water_well_thing):
    """Test creating a field parameters record with all fields."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
            field_parameter="pH",
            sample_value=7.4,
            units="SU",
            notes="Test notes",
            analyses_agency="NMBGMR",
            wc_lab_id="LAB-202",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.sample_pt_id == sample_info.sample_pt_id
        assert record.sample_point_id == sample_info.sample_point_id
        assert record.field_parameter == "pH"
        assert record.sample_value == 7.4

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_create_field_parameters_minimal(water_well_thing):
    """Test creating a field parameters record with minimal fields."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.global_id is not None
        assert record.sample_pt_id == sample_info.sample_pt_id
        assert record.field_parameter is None
        assert record.units is None
        assert record.sample_value == 0

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== READ tests ==========================
def test_read_field_parameters_by_global_id(water_well_thing):
    """Test reading a field parameters record by GlobalID."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMAFieldParameters, record.global_id)
        assert fetched is not None
        assert fetched.global_id == record.global_id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_query_field_parameters_by_sample_point_id(water_well_thing):
    """Test querying field parameters by sample_point_id."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record1 = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id=sample_info.sample_point_id,
        )
        record2 = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            sample_point_id="OTHER-PT",
        )
        session.add_all([record1, record2])
        session.commit()

        # Use SQLAlchemy 2.0 style select/execute for ORM queries.
        stmt = select(NMAFieldParameters).filter(
            NMAFieldParameters.sample_point_id == sample_info.sample_point_id
        )
        results = session.execute(stmt).scalars().all()
        assert len(results) >= 1
        assert all(r.sample_point_id == sample_info.sample_point_id for r in results)

        session.delete(record1)
        session.delete(record2)
        session.delete(sample_info)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_field_parameters(water_well_thing):
    """Test updating a field parameters record."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMAFieldParameters(
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
def test_delete_field_parameters(water_well_thing):
    """Test deleting a field parameters record."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
        )
        session.add(record)
        session.commit()

        session.delete(record)
        session.commit()

        fetched = session.get(NMAFieldParameters, record.global_id)
        assert fetched is None

        session.delete(sample_info)
        session.commit()


# ===================== Relational Integrity Tests ======================


def test_orphan_prevention_constraint():
    """
    VERIFIES: 'SamplePtID IS NOT NULL' and Foreign Key presence.
    Ensures the DB rejects records that aren't linked to a ChemistrySampleInfo.
    """
    with session_ctx() as session:
        orphan = NMAFieldParameters(
            field_parameter="pH",
            sample_value=7.0,
        )
        session.add(orphan)

        with pytest.raises((IntegrityError, ProgrammingError)):
            session.flush()
        session.rollback()


def test_cascade_delete_behavior(water_well_thing):
    """
    VERIFIES: 'on delete cascade' behavior.
    Deleting the parent sample must automatically remove associated field measurements.
    """
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        fp = NMAFieldParameters(
            sample_pt_id=sample_info.sample_pt_id,
            field_parameter="Temperature",
        )
        session.add(fp)
        session.commit()
        session.refresh(fp)
        fp_id = fp.global_id

        # Delete parent and check child
        session.delete(sample_info)
        session.commit()
        session.expire_all()

        assert (
            session.get(NMAFieldParameters, fp_id) is None
        ), "Child record persisted after parent deletion."


def test_update_cascade_propagation(water_well_thing):
    """
    VERIFIES: foreign key integrity on SamplePtID.
    Ensures the DB rejects updates to a non-existent parent SamplePtID.
    """
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        fp = NMAFieldParameters(
            global_id=uuid4(),
            sample_pt_id=sample_info.sample_pt_id,
            field_parameter="Dissolved Oxygen",
        )
        session.add(fp)
        session.commit()
        fp_id = fp.global_id

        with pytest.raises((IntegrityError, ProgrammingError)):
            fp.sample_pt_id = uuid4()
            session.flush()
        session.rollback()

        fetched = session.get(NMAFieldParameters, fp_id)
        if fetched is not None:
            session.delete(fetched)
        session.delete(sample_info)
        session.commit()
