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
        "id",                         # new PK
        "chemistry_sample_info_id",   # new FK (integer, not string)
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


def test_nma_minor_trace_chemistry_save_all_columns(water_well_thing):
    """Can save NMAMinorTraceChemistry with all columns populated."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry
    from datetime import date

    with session_ctx() as session:
        session.add(water_well_thing)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=water_well_thing.name,
            thing=water_well_thing,
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
        assert mtc.chemistry_sample_info_id == sample_info.object_id
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


def test_thing_has_chemistry_sample_infos_attribute(water_well_thing):
    """Thing should have chemistry_sample_infos relationship."""
    assert hasattr(water_well_thing, "chemistry_sample_infos")


def test_thing_chemistry_sample_infos_empty_by_default(water_well_thing):
    """New Thing should have empty chemistry_sample_infos."""
    with session_ctx() as session:
        session.add(water_well_thing)
        session.refresh(water_well_thing)

        assert water_well_thing.chemistry_sample_infos == []


def test_assign_thing_to_sample_info(water_well_thing):
    """Can assign Thing to ChemistrySampleInfo via object (not just ID)."""
    from db.nma_legacy import ChemistrySampleInfo

    with session_ctx() as session:
        session.add(water_well_thing)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=water_well_thing.name,
            thing=water_well_thing,  # OO: assign object
        )
        session.add(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == water_well_thing
        assert sample_info in water_well_thing.chemistry_sample_infos

        session.delete(sample_info)
        session.commit()


def test_append_sample_info_to_thing(water_well_thing):
    """Can append ChemistrySampleInfo to Thing's collection."""
    from db.nma_legacy import ChemistrySampleInfo

    with session_ctx() as session:
        session.add(water_well_thing)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=water_well_thing.name,
        )
        water_well_thing.chemistry_sample_infos.append(sample_info)
        session.commit()

        # Verify bidirectional
        assert sample_info.thing == water_well_thing
        assert sample_info.thing_id == water_well_thing.id

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
    from sqlalchemy.exc import IntegrityError

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="ORPHAN",
            # No thing - should fail
        )
        session.add(sample_info)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


# ===================== ChemistrySampleInfo → NMAMinorTraceChemistry association ==========================


def test_sample_info_has_minor_trace_chemistries_attribute():
    """ChemistrySampleInfo should have minor_trace_chemistries relationship."""
    from db.nma_legacy import ChemistrySampleInfo

    assert hasattr(ChemistrySampleInfo, "minor_trace_chemistries")


def test_sample_info_minor_trace_chemistries_empty_by_default():
    """New ChemistrySampleInfo should have empty minor_trace_chemistries."""
    from db.nma_legacy import ChemistrySampleInfo

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="TEST",
        )
        session.add(sample_info)
        session.commit()
        session.refresh(sample_info)

        assert sample_info.minor_trace_chemistries == []

        session.delete(sample_info)
        session.commit()


def test_assign_sample_info_to_mtc():
    """Can assign ChemistrySampleInfo to MinorTraceChemistry via object."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="TEST",
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


def test_append_mtc_to_sample_info():
    """Can append MinorTraceChemistry to ChemistrySampleInfo's collection."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="TEST",
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
        assert mtc.chemistry_sample_info_id == sample_info.object_id

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
    from sqlalchemy.exc import IntegrityError

    with session_ctx() as session:
        mtc = NMAMinorTraceChemistry(
            analyte="As",
            sample_value=0.01,
            units="mg/L",
            # No chemistry_sample_info - should fail
        )
        session.add(mtc)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()


# ===================== Full lineage navigation ==========================


def test_full_lineage_navigation(water_well_thing):
    """Can navigate full chain: mtc.chemistry_sample_info.thing"""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        session.add(water_well_thing)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=water_well_thing.name,
            thing=water_well_thing,
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
        assert mtc.chemistry_sample_info.thing == water_well_thing

        session.delete(sample_info)
        session.commit()


def test_reverse_lineage_navigation(water_well_thing):
    """Can navigate reverse: thing.chemistry_sample_infos[0].minor_trace_chemistries"""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        session.add(water_well_thing)

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=water_well_thing.name,
            thing=water_well_thing,
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

        # Reverse navigation
        assert len(water_well_thing.chemistry_sample_infos) == 1
        assert len(water_well_thing.chemistry_sample_infos[0].minor_trace_chemistries) == 1
        assert water_well_thing.chemistry_sample_infos[0].minor_trace_chemistries[0] == mtc

        session.delete(sample_info)
        session.commit()


# ===================== Cascade delete ==========================


def test_cascade_delete_sample_info_deletes_mtc():
    """Deleting ChemistrySampleInfo should cascade delete its MinorTraceChemistries."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="CASCADE-TEST",
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

        sample_info_id = sample_info.object_id
        assert session.query(NMAMinorTraceChemistry).filter_by(
            chemistry_sample_info_id=sample_info_id
        ).count() == 4

        # Delete parent
        session.delete(sample_info)
        session.commit()

        # Children should be gone
        assert session.query(NMAMinorTraceChemistry).filter_by(
            chemistry_sample_info_id=sample_info_id
        ).count() == 0


def test_cascade_delete_thing_deletes_sample_infos(water_well_thing):
    """Deleting Thing should cascade delete its ChemistrySampleInfos."""
    from db.nma_legacy import ChemistrySampleInfo
    from db import Thing

    with session_ctx() as session:
        # Create a separate thing for this test (don't delete the fixture)
        test_thing = Thing(
            name="Cascade Test Well",
            thing_type="water well",
            release_status="draft",
        )
        session.add(test_thing)
        session.commit()

        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id=test_thing.name,
            thing=test_thing,
        )
        session.add(sample_info)
        session.commit()

        thing_id = test_thing.id
        sample_info_id = sample_info.object_id

        # Delete thing
        session.delete(test_thing)
        session.commit()

        # Sample info should be gone
        assert session.get(ChemistrySampleInfo, sample_info_id) is None


# ===================== Multiple children ==========================


def test_multiple_sample_infos_per_thing(water_well_thing):
    """Thing can have multiple ChemistrySampleInfos."""
    from db.nma_legacy import ChemistrySampleInfo

    with session_ctx() as session:
        session.add(water_well_thing)

        for i in range(3):
            sample_info = ChemistrySampleInfo(
                object_id=_next_object_id(),
                sample_pt_id=f"TEST-{uuid4().hex[:8]}",
                sample_point_id=water_well_thing.name,
                thing=water_well_thing,
            )
            session.add(sample_info)
        session.commit()

        session.refresh(water_well_thing)
        assert len(water_well_thing.chemistry_sample_infos) == 3

        # Cleanup
        for si in water_well_thing.chemistry_sample_infos[:]:
            session.delete(si)
        session.commit()


def test_multiple_mtc_per_sample_info():
    """ChemistrySampleInfo can have multiple MinorTraceChemistries."""
    from db.nma_legacy import ChemistrySampleInfo, NMAMinorTraceChemistry

    with session_ctx() as session:
        sample_info = ChemistrySampleInfo(
            object_id=_next_object_id(),
            sample_pt_id=f"TEST-{uuid4().hex[:8]}",
            sample_point_id="MULTI-TEST",
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
