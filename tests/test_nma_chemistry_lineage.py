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

Lineage:
    Thing (1) ---> (*) ChemistrySampleInfo (1) ---> (*) NMAMinorTraceChemistry

Tests verify SQLAlchemy relationships enable OO navigation:
    - thing.chemistry_sample_infos
    - sample_info.thing
    - sample_info.minor_trace_chemistries
    - mtc.chemistry_sample_info
    - mtc.chemistry_sample_info.thing  (full chain)
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


@pytest.fixture(scope="module")
def shared_well():
    """Create a single Thing for all tests in this module."""
    from db import Thing

    with session_ctx() as session:
        thing = Thing(
            name=f"Shared-Well-{uuid4().hex[:8]}",
            thing_type="water well",
            release_status="draft",
        )
        session.add(thing)
        session.commit()
        session.refresh(thing)
        thing_id = thing.id

    yield thing_id

    # Cleanup after all tests
    with session_ctx() as session:
        thing = session.get(Thing, thing_id)
        if thing:
            session.delete(thing)
            session.commit()


# ===================== Model import tests ==========================


def test_models_importable():
    """Models should be importable from db.nma_legacy."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    assert ChemistrySampleInfo is not None
    assert NMAMinorTraceChemistry is not None


def test_nma_minor_trace_chemistry_table_name():
    """NMAMinorTraceChemistry should have correct table name."""
    from db.nma_legacy import NMAMinorTraceChemistry

    assert NMAMinorTraceChemistry.__tablename__ == "NMA_MinorTraceChemistry"


def test_nma_minor_trace_chemistry_columns():
    """
    NMAMinorTraceChemistry should have required columns.

    Omitted legacy columns: globalid, objectid, ssma_timestamp,
    samplepointid, sampleptid, wclab_id
    """
    from db.nma_legacy import NMAMinorTraceChemistry

    expected_columns = [
        "id",  # new PK
        "global_id",
        "chemistry_sample_info_id",  # new FK (UUID, not string)
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
        assert hasattr(NMAMinorTraceChemistry, col), f"Missing column: {col}"


def test_nma_minor_trace_chemistry_save_all_columns(shared_well):
    """Can save NMAMinorTraceChemistry with all columns populated."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing
    from datetime import date

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMAMinorTraceChemistry(
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
            volume=500.0,
            volume_unit="mL",
        )
        session.add(mtc)
        session.commit()
        session.refresh(mtc)

        # Verify all columns saved
        assert mtc.id is not None
        assert mtc.global_id is not None
        assert mtc.chemistry_sample_info_id == sample_info.sample_pt_id
        assert mtc.analyte == "As"
        assert mtc.sample_value == 0.015
        assert mtc.units == "mg/L"
        assert mtc.symbol == "<"
        assert mtc.analysis_method == "ICP-MS"
        assert mtc.analysis_date == date(2024, 6, 15)
        assert mtc.notes == "Test measurement"
        assert mtc.analyses_agency == "NMBGMR"
        assert mtc.uncertainty == 0.002
        assert mtc.volume == 500.0
        assert mtc.volume_unit == "mL"

        session.delete(sample_info)
        session.commit()


# ===================== Thing → ChemistrySampleInfo association ==========================


def test_thing_has_chemistry_sample_infos_attribute(shared_well):
    """Thing should have chemistry_sample_infos relationship."""
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)
        assert hasattr(well, "chemistry_sample_infos")


def test_thing_chemistry_sample_infos_empty_by_default():
    """New Thing should have empty chemistry_sample_infos."""
    from db import Thing

    with session_ctx() as session:
        # Create a fresh Thing for this test
        new_thing = Thing(
            name=f"Empty-Test-{uuid4().hex[:8]}",
            thing_type="water well",
            release_status="draft",
        )
        session.add(new_thing)
        session.commit()
        session.refresh(new_thing)

        assert new_thing.chemistry_sample_infos == []

        session.delete(new_thing)
        session.commit()


def test_assign_thing_to_sample_info(shared_well):
    """Can assign Thing to ChemistrySampleInfo via object (not just ID)."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,  # OO: assign object
        )
        session.add(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == well
        assert sample_info in well.chemistry_sample_infos

        session.delete(sample_info)
        session.commit()


def test_append_sample_info_to_thing(shared_well):
    """Can append ChemistrySampleInfo to Thing's collection."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
        )
        well.chemistry_sample_infos.append(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == well
        assert sample_info.thing_id == well.id

        session.delete(sample_info)
        session.commit()


# ===================== ChemistrySampleInfo → Thing association ==========================


def test_sample_info_has_thing_attribute():
    """ChemistrySampleInfo should have thing relationship."""
    from db.nma_legacy import ChemistrySampleInfo

    assert hasattr(ChemistrySampleInfo, "thing")


def test_sample_info_requires_thing():
    """ChemistrySampleInfo cannot be orphaned - must have a parent Thing."""
    from db.nma_legacy import ChemistrySampleInfo

    # Validator raises ValueError before database is even touched
    with pytest.raises(ValueError, match="requires a parent Thing"):
        ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing_id=None,  # Explicit None triggers validator
        )


# ===================== ChemistrySampleInfo → NMAMinorTraceChemistry association ==========================


def test_sample_info_has_minor_trace_chemistries_attribute():
    """ChemistrySampleInfo should have minor_trace_chemistries relationship."""
    from db.nma_legacy import ChemistrySampleInfo

    assert hasattr(ChemistrySampleInfo, "minor_trace_chemistries")


def test_sample_info_minor_trace_chemistries_empty_by_default(shared_well):
    """New ChemistrySampleInfo should have empty minor_trace_chemistries."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        assert sample_info.minor_trace_chemistries == []

        session.delete(sample_info)
        session.commit()


def test_assign_sample_info_to_mtc(shared_well):
    """Can assign ChemistrySampleInfo to MinorTraceChemistry via object."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMAMinorTraceChemistry(
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


def test_append_mtc_to_sample_info(shared_well):
    """Can append MinorTraceChemistry to ChemistrySampleInfo's collection."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMAMinorTraceChemistry(
            analyte="U",
            sample_value=15.2,
            units="ug/L",
        )
        sample_info.minor_trace_chemistries.append(mtc)
        session.commit()

        # Verify bidirectional
        assert mtc.chemistry_sample_info == sample_info
        assert mtc.chemistry_sample_info_id == sample_info.sample_pt_id

        session.delete(sample_info)
        session.commit()


# ===================== NMAMinorTraceChemistry → ChemistrySampleInfo association ==========================


def test_mtc_has_chemistry_sample_info_attribute():
    """NMAMinorTraceChemistry should have chemistry_sample_info relationship."""
    from db.nma_legacy import NMAMinorTraceChemistry

    assert hasattr(NMAMinorTraceChemistry, "chemistry_sample_info")


def test_mtc_requires_chemistry_sample_info():
    """NMAMinorTraceChemistry cannot be orphaned - must have a parent."""
    from db.nma_legacy import NMAMinorTraceChemistry

    # Validator raises ValueError before database is even touched
    with pytest.raises(ValueError, match="requires a parent ChemistrySampleInfo"):
        NMAMinorTraceChemistry(
            analyte="As",
            sample_value=0.01,
            units="mg/L",
            chemistry_sample_info_id=None,  # Explicit None triggers validator
        )


# ===================== Full lineage navigation ==========================


def test_full_lineage_navigation(shared_well):
    """Can navigate full chain: mtc.chemistry_sample_info.thing"""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMAMinorTraceChemistry(
            analyte="Se",
            sample_value=0.005,
            units="mg/L",
            chemistry_sample_info=sample_info,
        )
        session.add(mtc)
        session.commit()

        # Full chain navigation
        assert mtc.chemistry_sample_info.thing == well

        session.delete(sample_info)
        session.commit()


def test_reverse_lineage_navigation(shared_well):
    """Can navigate reverse: thing.chemistry_sample_infos[0].minor_trace_chemistries"""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        mtc = NMAMinorTraceChemistry(
            analyte="Pb",
            sample_value=0.002,
            units="mg/L",
            chemistry_sample_info=sample_info,
        )
        session.add(mtc)
        session.commit()
        session.refresh(well)

        # Reverse navigation - filter to just this sample_info
        matching = [
            si
            for si in well.chemistry_sample_infos
            if si.sample_pt_id == sample_info.sample_pt_id
        ]
        assert len(matching) == 1
        assert len(matching[0].minor_trace_chemistries) == 1
        assert matching[0].minor_trace_chemistries[0] == mtc

        session.delete(sample_info)
        session.commit()


# ===================== Cascade delete ==========================


def test_cascade_delete_sample_info_deletes_mtc(shared_well):
    """Deleting ChemistrySampleInfo should cascade delete its MinorTraceChemistries."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        # Add multiple children
        for analyte in ["As", "U", "Se", "Pb"]:
            sample_info.minor_trace_chemistries.append(
                NMAMinorTraceChemistry(
                    analyte=analyte,
                    sample_value=0.01,
                    units="mg/L",
                )
            )
        session.commit()

        sample_info_id = sample_info.sample_pt_id
        assert (
            session.query(NMAMinorTraceChemistry)
            .filter_by(chemistry_sample_info_id=sample_info_id)
            .count()
            == 4
        )

        # Delete parent
        session.delete(sample_info)
        session.commit()

        # Children should be gone
        assert (
            session.query(NMAMinorTraceChemistry)
            .filter_by(chemistry_sample_info_id=sample_info_id)
            .count()
            == 0
        )


def test_cascade_delete_thing_deletes_sample_infos():
    """Deleting Thing should cascade delete its ChemistrySampleInfos."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        # Create a separate thing for this test
        test_thing = Thing(
            name=f"Cascade-Test-{uuid4().hex[:8]}",
            thing_type="water well",
            release_status="draft",
        )
        session.add(test_thing)
        session.commit()

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=test_thing,
        )
        session.add(sample_info)
        session.commit()

        # SamplePtID is the PK for ChemistrySampleInfo.
        sample_info_id = sample_info.sample_pt_id

        # Delete thing
        session.delete(test_thing)
        session.commit()

    # Use fresh session to verify cascade delete (avoid session cache)
    with session_ctx() as session:
        assert session.get(ChemistrySampleInfo, sample_info_id) is None


# ===================== Multiple children ==========================


def test_multiple_sample_infos_per_thing():
    """Thing can have multiple ChemistrySampleInfos."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        # Create a dedicated thing for this test
        test_thing = Thing(
            name=f"Multi-SI-Test-{uuid4().hex[:8]}",
            thing_type="water well",
            release_status="draft",
        )
        session.add(test_thing)
        session.commit()

        for i in range(3):
            sample_info = ChemistrySampleInfo(
                object_id=_next_object_id(),
                sample_pt_id=_next_sample_pt_id(),
                sample_point_id=_next_sample_point_id(),
                thing=test_thing,
            )
            session.add(sample_info)
        session.commit()

        session.refresh(test_thing)
        assert len(test_thing.chemistry_sample_infos) == 3

        # Cleanup - delete thing cascades to sample_infos
        session.delete(test_thing)
        session.commit()


def test_multiple_mtc_per_sample_info(shared_well):
    """ChemistrySampleInfo can have multiple MinorTraceChemistries."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from db import Thing

    with session_ctx() as session:
        well = session.get(Thing, shared_well)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=_next_sample_pt_id(),
            sample_point_id=_next_sample_point_id(),
            thing=well,
        )
        session.add(sample_info)
        session.commit()

        analytes = ["As", "U", "Se", "Pb", "Cd", "Hg"]
        for analyte in analytes:
            sample_info.minor_trace_chemistries.append(
                NMAMinorTraceChemistry(
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
