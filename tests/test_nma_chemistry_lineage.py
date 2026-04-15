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
Unit tests for NMA Chemistry lineage OO associations.

Lineage (updated 2026-01):
    Thing (1) ---> (*) NMA_Chemistry_SampleInfo (1) ---> (*) NMA_MinorTraceChemistry

Tests verify SQLAlchemy relationships enable OO navigation:
    - thing.chemistry_sample_infos
    - sample_info.thing
    - sample_info.minor_trace_chemistries
    - mtc.chemistry_sample_info
    - mtc.chemistry_sample_info.thing  (full chain)

FK Change (2026-01):
    - Uses thing_id (Integer FK to Thing.id)
"""

from uuid import uuid4

import pytest

from db.engine import session_ctx


def _next_object_id() -> int:
    """Generate unique negative ID to avoid collision with legacy data."""
    return -(uuid4().int % 2_000_000_000)


def _next_sample_pt_id():
    return uuid4()


def _next_sample_point_id() -> str:
    return f"SP-{uuid4().hex[:7]}"


def _next_global_id():
    return uuid4()


@pytest.fixture(scope="module")
def shared_thing():
    """Create a single Thing (with Location) for all tests in this module."""
    from db import Location, LocationThingAssociation, Thing

    with session_ctx() as session:
        location = Location(
            point="POINT(-107.949533 33.809665)",
            elevation=2464.9,
            release_status="draft",
        )
        session.add(location)
        session.commit()
        session.refresh(location)

        thing = Thing(
            name="LINEAGE-TEST-WELL",
            thing_type="monitoring well",
            release_status="draft",
        )
        session.add(thing)
        session.commit()
        session.refresh(thing)

        assoc = LocationThingAssociation(
            location_id=location.id,
            thing_id=thing.id,
        )
        session.add(assoc)
        session.commit()

        thing_id = thing.id
        location_id = location.id

    yield thing_id

    # Cleanup after all tests
    with session_ctx() as session:
        thing = session.get(Thing, thing_id)
        location = session.get(Location, location_id)
        if thing:
            session.delete(thing)
        if location:
            session.delete(location)
        session.commit()


# ===================== Model import tests ==========================


def test_models_importable():
    """Models should be importable from db.nma_legacy."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry

    assert NMA_Chemistry_SampleInfo is not None
    assert NMA_MinorTraceChemistry is not None


def test_nma_minor_trace_chemistry_table_name():
    """NMA_MinorTraceChemistry should have correct table name."""
    from db.nma_legacy import NMA_MinorTraceChemistry

    assert NMA_MinorTraceChemistry.__tablename__ == "NMA_MinorTraceChemistry"


def test_nma_minor_trace_chemistry_columns():
    """
    NMA_MinorTraceChemistry should have required columns.

    Updated for Integer PK schema:
    - id: Integer PK (autoincrement)
    - nma_global_id: Legacy GlobalID UUID (UNIQUE)
    - chemistry_sample_info_id: Integer FK to NMA_Chemistry_SampleInfo.id
    """
    from db.nma_legacy import NMA_MinorTraceChemistry

    expected_columns = [
        "id",  # Integer PK
        "nma_global_id",  # Legacy UUID
        "chemistry_sample_info_id",  # Integer FK
        "nma_sample_point_id",  # Legacy sample point id
        # from legacy
        "analyte",
        "sample_value",
        "units",
        "symbol",
        "analysis_method",
        "analysis_date",
        "notes",
        "analyses_agency",
        "uncertainty",
        "volume",
        "volume_unit",
    ]

    for col in expected_columns:
        assert hasattr(NMA_MinorTraceChemistry, col), f"Missing column: {col}"


def test_nma_minor_trace_chemistry_save_all_columns(shared_thing):
    """Can save NMA_MinorTraceChemistry with all columns populated."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing
    from datetime import date

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="As",
            sample_value=0.015,
            units="mg/L",
            symbol="<",
            analysis_method="ICP-MS",
            analysis_date=date(2024, 6, 15),
            notes="Test measurement",
            analyses_agency="NMBGMR",
            uncertainty=0.002,
            volume=500,
            volume_unit="mL",
        )
        session.add(mtc)
        session.commit()
        session.refresh(mtc)

        # Verify all columns saved
        assert mtc.id is not None  # Integer PK
        assert mtc.nma_global_id is not None  # Legacy UUID
        assert mtc.chemistry_sample_info_id == sample_info.id  # Integer FK
        assert mtc.nma_sample_point_id == sample_info.nma_sample_point_id
        assert mtc.analyte == "As"
        assert mtc.sample_value == 0.015
        assert mtc.units == "mg/L"
        assert mtc.symbol == "<"
        assert mtc.analysis_method == "ICP-MS"
        assert mtc.analysis_date == date(2024, 6, 15)
        assert mtc.notes == "Test measurement"
        assert mtc.analyses_agency == "NMBGMR"
        assert mtc.uncertainty == 0.002
        assert mtc.volume == 500
        assert mtc.volume_unit == "mL"

        session.delete(sample_info)
        session.commit()


# ===================== Thing → NMA_Chemistry_SampleInfo association ==========================


def test_thing_has_chemistry_sample_infos_attribute(shared_thing):
    """Thing should have chemistry_sample_infos relationship."""
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)
        assert hasattr(thing, "chemistry_sample_infos")


def test_thing_chemistry_sample_infos_empty_by_default():
    """New Thing should have empty chemistry_sample_infos."""
    from db import Thing, Location, LocationThingAssociation

    with session_ctx() as session:
        # Create a fresh Thing for this test
        location = Location(
            point="POINT(-106.0 35.0)",
            elevation=1500.0,
            release_status="draft",
        )
        session.add(location)
        session.commit()

        new_thing = Thing(
            name="EMPTY-CHEM-TEST",
            thing_type="monitoring well",
            release_status="draft",
        )
        session.add(new_thing)
        session.commit()

        assoc = LocationThingAssociation(
            location_id=location.id,
            thing_id=new_thing.id,
        )
        session.add(assoc)
        session.commit()
        session.refresh(new_thing)

        assert new_thing.chemistry_sample_infos == []

        session.delete(new_thing)
        session.delete(location)
        session.commit()


def test_assign_thing_to_sample_info(shared_thing):
    """Can assign Thing to NMA_Chemistry_SampleInfo via object (not just ID)."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,  # OO: assign object
        )
        session.add(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == thing
        assert sample_info in thing.chemistry_sample_infos

        session.delete(sample_info)
        session.commit()


def test_append_sample_info_to_thing(shared_thing):
    """Can append NMA_Chemistry_SampleInfo to Thing's collection."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
        )
        thing.chemistry_sample_infos.append(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == thing
        assert sample_info.thing_id == thing.id

        session.delete(sample_info)
        session.commit()


def test_sample_info_has_thing_attribute(shared_thing):
    """NMA_Chemistry_SampleInfo should have thing relationship."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        assert hasattr(sample_info, "thing")
        assert sample_info.thing == thing

        session.delete(sample_info)
        session.commit()


def test_sample_info_requires_thing(shared_thing):
    """NMA_Chemistry_SampleInfo should require thing_id (not nullable)."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from sqlalchemy.exc import IntegrityError, ProgrammingError

    with session_ctx() as session:
        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            # No thing_id - should fail
        )
        session.add(sample_info)
        # Driver may surface NOT NULL violations as ProgrammingError (code 23502)
        with pytest.raises((IntegrityError, ProgrammingError, ValueError)):
            session.commit()
        session.rollback()


# ===================== NMA_Chemistry_SampleInfo → NMA_MinorTraceChemistry association ==========================


def test_sample_info_minor_trace_chemistries_empty_by_default(shared_thing):
    """New NMA_Chemistry_SampleInfo should have empty minor_trace_chemistries."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        assert sample_info.minor_trace_chemistries == []

        session.delete(sample_info)
        session.commit()


def test_assign_sample_info_to_mtc(shared_thing):
    """Can assign NMA_Chemistry_SampleInfo to NMA_MinorTraceChemistry via object."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,  # OO: assign object
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Pb",
        )
        session.add(mtc)
        session.commit()

        # Verify bidirectional
        assert mtc.chemistry_sample_info == sample_info
        assert mtc in sample_info.minor_trace_chemistries

        session.delete(sample_info)
        session.commit()


def test_append_mtc_to_sample_info(shared_thing):
    """Can append NMA_MinorTraceChemistry to NMA_Chemistry_SampleInfo's collection."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Fe",
        )
        sample_info.minor_trace_chemistries.append(mtc)
        session.commit()

        # Verify bidirectional
        assert mtc.chemistry_sample_info == sample_info
        assert mtc.chemistry_sample_info_id == sample_info.id

        session.delete(sample_info)
        session.commit()


def test_mtc_requires_chemistry_sample_info():
    """NMA_MinorTraceChemistry should require chemistry_sample_info_id."""
    from db.nma_legacy import NMA_MinorTraceChemistry
    from sqlalchemy.exc import IntegrityError, ProgrammingError

    with session_ctx() as session:
        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            nma_sample_point_id=_next_sample_point_id(),
            analyte="Cu",
            # No chemistry_sample_info_id - should fail
        )
        session.add(mtc)
        # Driver may surface NOT NULL violations as ProgrammingError (code 23502)
        with pytest.raises((IntegrityError, ProgrammingError)):
            session.commit()
        session.rollback()


# ===================== Full lineage navigation ==========================


def test_full_lineage_navigation(shared_thing):
    """Can navigate full lineage: Thing -> SampleInfo -> MTC."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Zn",
        )
        session.add(mtc)
        session.commit()

        # Forward navigation
        assert thing.chemistry_sample_infos[0] == sample_info
        assert sample_info.minor_trace_chemistries[0] == mtc

        # Reverse navigation
        assert mtc.chemistry_sample_info == sample_info
        assert mtc.chemistry_sample_info.thing == thing

        session.delete(sample_info)
        session.commit()


def test_reverse_lineage_navigation(shared_thing):
    """Can navigate reverse: MTC -> SampleInfo -> Thing."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Mn",
        )
        session.add(mtc)
        session.commit()
        session.refresh(mtc)

        # Full reverse chain
        assert mtc.chemistry_sample_info.thing.id == thing.id

        session.delete(sample_info)
        session.commit()


# ===================== Cascade delete tests ==========================


def test_cascade_delete_sample_info_deletes_mtc(shared_thing):
    """Deleting NMA_Chemistry_SampleInfo should cascade delete NMA_MinorTraceChemistry."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Cd",
        )
        session.add(mtc)
        session.commit()

        mtc_id = mtc.id
        session.delete(sample_info)
        session.commit()
        session.expire_all()  # Force fresh DB lookup after cascade delete

        # MTC should be gone
        assert session.get(NMA_MinorTraceChemistry, mtc_id) is None


def test_cascade_delete_thing_deletes_sample_infos(shared_thing):
    """Deleting Thing should cascade delete NMA_Chemistry_SampleInfo."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing, Location, LocationThingAssociation

    with session_ctx() as session:
        # Create a separate thing for this test
        location = Location(
            point="POINT(-105.0 34.0)",
            elevation=1200.0,
            release_status="draft",
        )
        session.add(location)
        session.commit()

        thing = Thing(
            name="CASCADE-DELETE-TEST",
            thing_type="monitoring well",
            release_status="draft",
        )
        session.add(thing)
        session.commit()

        assoc = LocationThingAssociation(
            location_id=location.id,
            thing_id=thing.id,
        )
        session.add(assoc)
        session.commit()

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        sample_info_id = sample_info.id
        session.delete(thing)
        session.commit()
        session.expire_all()  # Force fresh DB lookup after cascade delete

        # SampleInfo should be gone
        assert session.get(NMA_Chemistry_SampleInfo, sample_info_id) is None

        session.delete(location)
        session.commit()


# ===================== Multiple records tests ==========================


def test_multiple_sample_infos_per_thing(shared_thing):
    """Thing can have multiple NMA_Chemistry_SampleInfo records."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info1 = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        sample_info2 = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add_all([sample_info1, sample_info2])
        session.commit()
        session.refresh(thing)

        assert len(thing.chemistry_sample_infos) >= 2
        assert sample_info1 in thing.chemistry_sample_infos
        assert sample_info2 in thing.chemistry_sample_infos

        session.delete(sample_info1)
        session.delete(sample_info2)
        session.commit()


def test_multiple_mtc_per_sample_info(shared_thing):
    """NMA_Chemistry_SampleInfo can have multiple NMA_MinorTraceChemistry records."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        thing = session.get(Thing, shared_thing)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            thing=thing,
        )
        session.add(sample_info)
        session.commit()

        mtc1 = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="As",
        )
        mtc2 = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
            nma_sample_point_id=sample_info.nma_sample_point_id,
            analyte="Pb",
        )
        session.add_all([mtc1, mtc2])
        session.commit()
        session.refresh(sample_info)

        assert len(sample_info.minor_trace_chemistries) == 2
        assert mtc1 in sample_info.minor_trace_chemistries
        assert mtc2 in sample_info.minor_trace_chemistries

        session.delete(sample_info)
        session.commit()


# ============= EOF =============================================
