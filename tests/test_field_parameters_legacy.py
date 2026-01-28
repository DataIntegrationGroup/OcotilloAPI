"""
Unit tests for NMA_FieldParameters legacy model.

These tests verify the migration of columns from the legacy NMA_FieldParameters table.

Updated for Integer PK schema:
- id: Integer PK (autoincrement)
- nma_global_id: Legacy GlobalID UUID (UNIQUE)
- chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
- nma_sample_pt_id: Legacy SamplePtID UUID (for audit)
- nma_sample_point_id: Legacy SamplePointID string
- nma_object_id: Legacy OBJECTID (UNIQUE)
- nma_wclab_id: Legacy WCLab_ID string
"""

from uuid import uuid4

import pytest
from sqlalchemy import select, inspect
from sqlalchemy.exc import IntegrityError, ProgrammingError

from db.engine import session_ctx
from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_FieldParameters


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


def _create_sample_info(session, water_well_thing) -> NMA_Chemistry_SampleInfo:
    sample = NMA_Chemistry_SampleInfo(
        nma_sample_pt_id=uuid4(),
        nma_sample_point_id=_next_sample_point_id(),
        thing_id=water_well_thing.id,
    )
    session.add(sample)
    session.commit()
    session.refresh(sample)
    return sample


# ===================== Table and Column Existence Tests ==========================


def test_field_parameters_has_all_migrated_columns():
    """
    VERIFIES: The SQLAlchemy model matches the migration mapping contract.
    This ensures all Python-side attribute names exist as expected in the ORM.
    """
    mapper = inspect(NMA_FieldParameters)
    actual_columns = [column.key for column in mapper.attrs]

    expected_columns = [
        "id",
        "nma_global_id",
        "chemistry_sample_info_id",
        "nma_sample_pt_id",
        "nma_sample_point_id",
        "field_parameter",
        "sample_value",
        "units",
        "notes",
        "nma_object_id",
        "analyses_agency",
        "nma_wclab_id",
    ]

    for column in expected_columns:
        assert column in actual_columns, f"Model is missing expected column: {column}"


def test_field_parameters_table_name():
    """Test that the table name follows convention."""
    assert NMA_FieldParameters.__tablename__ == "NMA_FieldParameters"


# ===================== Functional & CRUD Tests =========================


def test_field_parameters_persistence(water_well_thing):
    """
    Verifies that data correctly persists and retrieves for the core columns.
    This confirms the Postgres data types (REAL, UUID, VARCHAR) are compatible.
    """
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        test_global_id = uuid4()
        new_fp = NMA_FieldParameters(
            nma_global_id=test_global_id,
            chemistry_sample_info_id=sample_info.id,
            nma_sample_pt_id=sample_info.nma_sample_pt_id,
            nma_sample_point_id="PT-123",
            field_parameter="pH",
            sample_value=7.4,
            units="SU",
            notes="Legacy migration verification",
            analyses_agency="NMA Agency",
            nma_wclab_id="WCLAB-01",
        )

        session.add(new_fp)
        session.commit()
        session.expire_all()

        retrieved = session.get(NMA_FieldParameters, new_fp.id)
        assert retrieved.sample_value == 7.4
        assert retrieved.field_parameter == "pH"
        assert retrieved.units == "SU"
        assert retrieved.analyses_agency == "NMA Agency"

        session.delete(new_fp)
        session.delete(sample_info)
        session.commit()


def test_object_id_column_exists(water_well_thing):
    """Verifies that the nma_object_id column exists."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        fp1 = NMA_FieldParameters(
            chemistry_sample_info_id=sample_info.id,
            field_parameter="Temp",
        )
        session.add(fp1)
        session.commit()
        session.refresh(fp1)

        # nma_object_id is nullable
        assert fp1.id is not None  # Integer PK auto-generated
        assert hasattr(fp1, "nma_object_id")

        session.delete(fp1)
        session.delete(sample_info)
        session.commit()


# ===================== CREATE tests ==========================
def test_create_field_parameters_all_fields(water_well_thing):
    """Test creating a field parameters record with all fields."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_pt_id=sample_info.nma_sample_pt_id,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            field_parameter="pH",
            sample_value=7.4,
            units="SU",
            notes="Test notes",
            analyses_agency="NMBGMR",
            nma_wclab_id="LAB-202",
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.chemistry_sample_info_id == sample_info.id
        assert record.nma_sample_pt_id == sample_info.nma_sample_pt_id
        assert record.nma_sample_point_id == sample_info.nma_sample_point_id
        assert record.field_parameter == "pH"
        assert record.sample_value == 7.4

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_create_field_parameters_minimal(water_well_thing):
    """Test creating a field parameters record with minimal fields."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        assert record.id is not None  # Integer PK auto-generated
        assert record.nma_global_id is not None
        assert record.chemistry_sample_info_id == sample_info.id
        assert record.field_parameter is None
        assert record.units is None
        assert record.sample_value is None

        session.delete(record)
        session.delete(sample_info)
        session.commit()


# ===================== READ tests ==========================
def test_read_field_parameters_by_id(water_well_thing):
    """Test reading a field parameters record by Integer ID."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()

        fetched = session.get(NMA_FieldParameters, record.id)
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.nma_global_id == record.nma_global_id

        session.delete(record)
        session.delete(sample_info)
        session.commit()


def test_query_field_parameters_by_nma_sample_point_id(water_well_thing):
    """Test querying field parameters by nma_sample_point_id."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record1 = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_point_id=sample_info.nma_sample_point_id,
        )
        record2 = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            nma_sample_point_id="OTHER-PT",
        )
        session.add_all([record1, record2])
        session.commit()

        # Use SQLAlchemy 2.0 style select/execute for ORM queries.
        stmt = select(NMA_FieldParameters).filter(
            NMA_FieldParameters.nma_sample_point_id == sample_info.nma_sample_point_id
        )
        results = session.execute(stmt).scalars().all()
        assert len(results) >= 1
        assert all(
            r.nma_sample_point_id == sample_info.nma_sample_point_id for r in results
        )

        session.delete(record1)
        session.delete(record2)
        session.delete(sample_info)
        session.commit()


# ===================== UPDATE tests ==========================
def test_update_field_parameters(water_well_thing):
    """Test updating a field parameters record."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMA_FieldParameters(
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
def test_delete_field_parameters(water_well_thing):
    """Test deleting a field parameters record."""
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        record = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
        )
        session.add(record)
        session.commit()
        record_id = record.id

        session.delete(record)
        session.commit()

        fetched = session.get(NMA_FieldParameters, record_id)
        assert fetched is None

        session.delete(sample_info)
        session.commit()


# ===================== Relational Integrity Tests ======================


def test_orphan_prevention_constraint():
    """
    VERIFIES: 'chemistry_sample_info_id IS NOT NULL' and Foreign Key presence.
    Ensures the DB rejects records that aren't linked to a NMA_Chemistry_SampleInfo.
    """
    with session_ctx() as session:
        orphan = NMA_FieldParameters(
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
        fp = NMA_FieldParameters(
            chemistry_sample_info_id=sample_info.id,
            field_parameter="Temperature",
        )
        session.add(fp)
        session.commit()
        session.refresh(fp)
        fp_id = fp.id

        # Delete parent and check child
        session.delete(sample_info)
        session.commit()
        session.expire_all()

        assert (
            session.get(NMA_FieldParameters, fp_id) is None
        ), "Child record persisted after parent deletion."


def test_update_cascade_propagation(water_well_thing):
    """
    VERIFIES: foreign key integrity on chemistry_sample_info_id.
    Ensures the DB rejects updates to a non-existent parent.
    """
    with session_ctx() as session:
        sample_info = _create_sample_info(session, water_well_thing)
        fp = NMA_FieldParameters(
            nma_global_id=uuid4(),
            chemistry_sample_info_id=sample_info.id,
            field_parameter="Dissolved Oxygen",
        )
        session.add(fp)
        session.commit()
        fp_id = fp.id

        with pytest.raises((IntegrityError, ProgrammingError)):
            fp.chemistry_sample_info_id = 999999  # Non-existent ID
            session.flush()
        session.rollback()

        fetched = session.get(NMA_FieldParameters, fp_id)
        if fetched is not None:
            session.delete(fetched)
        session.delete(sample_info)
        session.commit()


# ===================== Integer PK tests ==========================


def test_field_parameters_has_integer_pk():
    """NMA_FieldParameters.id is Integer PK."""
    from sqlalchemy import Integer

    col = NMA_FieldParameters.__table__.c.id
    assert col.primary_key is True
    assert isinstance(col.type, Integer)


def test_field_parameters_nma_global_id_is_unique():
    """NMA_FieldParameters.nma_global_id is UNIQUE."""
    # Use database column name (nma_GlobalID), not Python attribute name
    col = NMA_FieldParameters.__table__.c["nma_GlobalID"]
    assert col.unique is True


def test_field_parameters_chemistry_sample_info_fk():
    """NMA_FieldParameters.chemistry_sample_info_id is Integer FK."""
    col = NMA_FieldParameters.__table__.c.chemistry_sample_info_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    assert "NMA_Chemistry_SampleInfo.id" in str(fks[0].target_fullname)
