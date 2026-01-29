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
    Location (1) ---> (*) NMA_Chemistry_SampleInfo (1) ---> (*) NMA_MinorTraceChemistry

Tests verify SQLAlchemy relationships enable OO navigation:
    - location.chemistry_sample_infos
    - sample_info.location
    - sample_info.minor_trace_chemistries
    - mtc.chemistry_sample_info
    - mtc.chemistry_sample_info.location  (full chain)

FK Change (2026-01):
    - Changed from thing_id to location_id
    - 99.95% of chemistry records have valid LocationId -> Location match
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
def shared_location():
    """Create a single Location for all tests in this module."""
    from db import Location

    with session_ctx() as session:
        location = Location(
            point="POINT(-107.949533 33.809665)",
            elevation=2464.9,
            release_status="draft",
        )
        session.add(location)
        session.commit()
        session.refresh(location)
        location_id = location.id

    yield location_id

    # Cleanup after all tests
    with session_ctx() as session:
        location = session.get(Location, location_id)
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


def test_nma_minor_trace_chemistry_save_all_columns(shared_location):
    """Can save NMA_MinorTraceChemistry with all columns populated."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location
    from datetime import date

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            chemistry_sample_info=sample_info,
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


# ===================== Location → NMA_Chemistry_SampleInfo association ==========================


def test_location_has_chemistry_sample_infos_attribute(shared_location):
    """Location should have chemistry_sample_infos relationship."""
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)
        assert hasattr(location, "chemistry_sample_infos")


def test_location_chemistry_sample_infos_empty_by_default():
    """New Location should have empty chemistry_sample_infos."""
    from db import Location

    with session_ctx() as session:
        # Create a fresh Location for this test
        new_location = Location(
            point="POINT(-106.0 35.0)",
            elevation=1500.0,
            release_status="draft",
        )
        session.add(new_location)
        session.commit()
        session.refresh(new_location)

        assert new_location.chemistry_sample_infos == []

        session.delete(new_location)
        session.commit()


def test_assign_location_to_sample_info(shared_location):
    """Can assign Location to NMA_Chemistry_SampleInfo via object (not just ID)."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,  # OO: assign object
        )
        session.add(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.location == location
        assert sample_info in location.chemistry_sample_infos

        session.delete(sample_info)
        session.commit()


def test_append_sample_info_to_location(shared_location):
    """Can append NMA_Chemistry_SampleInfo to Location's collection."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
        )
        location.chemistry_sample_infos.append(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.location == location
        assert sample_info.location_id == location.id

        session.delete(sample_info)
        session.commit()


# ===================== NMA_Chemistry_SampleInfo → Location association ==========================


def test_sample_info_has_location_attribute():
    """NMA_Chemistry_SampleInfo should have location relationship."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo

    assert hasattr(NMA_Chemistry_SampleInfo, "location")


def test_sample_info_requires_location():
    """NMA_Chemistry_SampleInfo cannot be orphaned - must have a parent Location."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo

    # Validator raises ValueError before database is even touched
    with pytest.raises(ValueError, match="requires a parent Location"):
        NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location_id=None,  # Explicit None triggers validator
        )


# ===================== NMA_Chemistry_SampleInfo → NMA_MinorTraceChemistry association ==========================


def test_sample_info_has_minor_trace_chemistries_attribute():
    """NMA_Chemistry_SampleInfo should have minor_trace_chemistries relationship."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo

    assert hasattr(NMA_Chemistry_SampleInfo, "minor_trace_chemistries")


def test_sample_info_minor_trace_chemistries_empty_by_default(shared_location):
    """New NMA_Chemistry_SampleInfo should have empty minor_trace_chemistries."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        assert sample_info.minor_trace_chemistries == []

        session.delete(sample_info)
        session.commit()


def test_assign_sample_info_to_mtc(shared_location):
    """Can assign NMA_Chemistry_SampleInfo to MinorTraceChemistry via object."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            analyte="As",
            sample_value=0.01,
            units="mg/L",
            chemistry_sample_info=sample_info,  # OO: assign object
        )
        session.add(mtc)
        session.commit()

        # Verify bidirectional
        assert mtc.chemistry_sample_info == sample_info
        assert mtc in sample_info.minor_trace_chemistries

        session.delete(sample_info)  # cascades to mtc
        session.commit()


def test_append_mtc_to_sample_info(shared_location):
    """Can append MinorTraceChemistry to NMA_Chemistry_SampleInfo's collection."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            analyte="U",
            sample_value=15.2,
            units="ug/L",
        )
        sample_info.minor_trace_chemistries.append(mtc)
        session.commit()

        # Verify bidirectional
        assert mtc.chemistry_sample_info == sample_info
        assert mtc.chemistry_sample_info_id == sample_info.id  # Integer FK

        session.delete(sample_info)
        session.commit()


# ===================== NMA_MinorTraceChemistry → NMA_Chemistry_SampleInfo association ==========================


def test_mtc_has_chemistry_sample_info_attribute():
    """NMA_MinorTraceChemistry should have chemistry_sample_info relationship."""
    from db.nma_legacy import NMA_MinorTraceChemistry

    assert hasattr(NMA_MinorTraceChemistry, "chemistry_sample_info")


def test_mtc_requires_chemistry_sample_info():
    """NMA_MinorTraceChemistry cannot be orphaned - must have a parent."""
    from db.nma_legacy import NMA_MinorTraceChemistry

    # Validator raises ValueError before database is even touched
    with pytest.raises(ValueError, match="requires a parent NMA_Chemistry_SampleInfo"):
        NMA_MinorTraceChemistry(
            analyte="As",
            sample_value=0.01,
            units="mg/L",
            chemistry_sample_info_id=None,  # Explicit None triggers validator
        )


# ===================== Full lineage navigation ==========================


def test_full_lineage_navigation(shared_location):
    """Can navigate full chain: mtc.chemistry_sample_info.location"""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            analyte="Se",
            sample_value=0.005,
            units="mg/L",
            chemistry_sample_info=sample_info,
        )
        session.add(mtc)
        session.commit()

        # Full chain navigation
        assert mtc.chemistry_sample_info.location == location

        session.delete(sample_info)
        session.commit()


def test_reverse_lineage_navigation(shared_location):
    """Can navigate reverse: location.chemistry_sample_infos[0].minor_trace_chemistries"""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMA_MinorTraceChemistry(
            nma_global_id=_next_global_id(),
            analyte="Pb",
            sample_value=0.002,
            units="mg/L",
            chemistry_sample_info=sample_info,
        )
        session.add(mtc)
        session.commit()
        session.refresh(location)

        # Reverse navigation - filter to just this sample_info
        matching = [si for si in location.chemistry_sample_infos if si.id == sample_info.id]
        assert len(matching) == 1
        assert len(matching[0].minor_trace_chemistries) == 1
        assert matching[0].minor_trace_chemistries[0] == mtc

        session.delete(sample_info)
        session.commit()


# ===================== Cascade delete ==========================


def test_cascade_delete_sample_info_deletes_mtc(shared_location):
    """Deleting NMA_Chemistry_SampleInfo should cascade delete its MinorTraceChemistries."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        # Add multiple children
        for analyte in ["As", "U", "Se", "Pb"]:
            sample_info.minor_trace_chemistries.append(
                NMA_MinorTraceChemistry(
                    nma_global_id=_next_global_id(),
                    analyte=analyte,
                    sample_value=0.01,
                    units="mg/L",
                )
            )
        session.commit()

        sample_info_id = sample_info.id  # Integer PK
        assert (
            session.query(NMA_MinorTraceChemistry)
            .filter_by(chemistry_sample_info_id=sample_info_id)
            .count()
            == 4
        )

        # Delete parent
        session.delete(sample_info)
        session.commit()

        # Children should be gone
        assert (
            session.query(NMA_MinorTraceChemistry)
            .filter_by(chemistry_sample_info_id=sample_info_id)
            .count()
            == 0
        )


def test_cascade_delete_location_deletes_sample_infos():
    """Deleting Location should cascade delete its NMA_Chemistry_SampleInfos."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Location

    with session_ctx() as session:
        # Create a separate location for this test
        test_location = Location(
            point="POINT(-105.5 34.5)",
            elevation=1800.0,
            release_status="draft",
        )
        session.add(test_location)
        session.commit()

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=test_location,
        )
        session.add(sample_info)
        session.commit()

        sample_info_id = sample_info.id  # Integer PK

        # Delete location
        session.delete(test_location)
        session.commit()

    # Use fresh session to verify cascade delete (avoid session cache)
    with session_ctx() as session:
        assert session.get(NMA_Chemistry_SampleInfo, sample_info_id) is None


# ===================== Multiple children ==========================


def test_multiple_sample_infos_per_location():
    """Location can have multiple NMA_Chemistry_SampleInfos."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo
    from db import Location

    with session_ctx() as session:
        # Create a dedicated location for this test
        test_location = Location(
            point="POINT(-106.5 35.5)",
            elevation=2000.0,
            release_status="draft",
        )
        session.add(test_location)
        session.commit()

        for i in range(3):
            sample_info = NMA_Chemistry_SampleInfo(
                nma_object_id=_next_object_id(),
                nma_sample_pt_id=_next_sample_pt_id(),
                nma_sample_point_id=_next_sample_point_id(),
                location=test_location,
            )
            session.add(sample_info)
        session.commit()

        session.refresh(test_location)
        assert len(test_location.chemistry_sample_infos) == 3

        # Cleanup - delete location cascades to sample_infos
        session.delete(test_location)
        session.commit()


def test_multiple_mtc_per_sample_info(shared_location):
    """NMA_Chemistry_SampleInfo can have multiple MinorTraceChemistries."""
    from db.nma_legacy import NMA_Chemistry_SampleInfo, NMA_MinorTraceChemistry
    from db import Location

    with session_ctx() as session:
        location = session.get(Location, shared_location)

        sample_info = NMA_Chemistry_SampleInfo(
            nma_object_id=_next_object_id(),
            nma_sample_pt_id=_next_sample_pt_id(),
            nma_sample_point_id=_next_sample_point_id(),
            location=location,
        )
        session.add(sample_info)
        session.commit()

        analytes = ["As", "U", "Se", "Pb", "Cd", "Hg"]
        for analyte in analytes:
            sample_info.minor_trace_chemistries.append(
                NMA_MinorTraceChemistry(
                    nma_global_id=_next_global_id(),
                    analyte=analyte,
                    sample_value=0.01,
                    units="mg/L",
                )
            )
        session.commit()

        session.refresh(sample_info)
        assert len(sample_info.minor_trace_chemistries) == 6

        session.delete(sample_info)
        session.commit()


# ============= EOF =============================================
