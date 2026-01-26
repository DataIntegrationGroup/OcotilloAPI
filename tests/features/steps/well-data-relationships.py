# ===============================================================================
# Copyright 2026
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
Step definitions for Well Data Relationships feature tests.
Tests FK relationships, orphan prevention, and cascade delete behavior.
"""

import uuid
from datetime import datetime

from behave import given, when, then
from behave.runner import Context
from sqlalchemy.exc import IntegrityError, StatementError

from db import Thing
from db.engine import session_ctx
from db.nma_legacy import (
    NMA_Chemistry_SampleInfo,
    NMA_HydraulicsData,
    NMA_NMA_Stratigraphy,
    NMA_Radionuclides,
    NMA_NMA_AssociatedData,
    NMA_Soil_Rock_Results,
)


@given("the Ocotillo database is set up")
def step_given_database_setup(context: Context):
    """Ensure database is ready for testing."""
    # Database connection is handled by session_ctx
    context.test_wells = []
    context.test_records = {}


@given("a well record exists")
def step_given_well_exists(context: Context):
    """Create a test well (Thing) record."""
    with session_ctx() as session:
        well = Thing(
            name=f"TEST_WELL_{uuid.uuid4().hex[:8]}",
            thing_type="water well",
            release_status="public",
            nma_pk_welldata=str(uuid.uuid4()),
            nma_pk_location=str(uuid.uuid4()),
        )
        session.add(well)
        session.commit()
        session.refresh(well)
        context.test_well = well
        context.test_well_id = well.id
        if not hasattr(context, "test_wells"):
            context.test_wells = []
        context.test_wells.append(well)


@then("the well can store its original NM_Aquifer WellID")
def step_then_well_stores_wellid(context: Context):
    """Verify well can store legacy WellID."""
    assert (
        context.test_well.nma_pk_welldata is not None
    ), "Well should store legacy WellID"
    assert isinstance(
        context.test_well.nma_pk_welldata, str
    ), "WellID should be a string"


@then("the well can be found by its legacy WellID")
def step_then_find_by_wellid(context: Context):
    """Verify well can be queried by legacy WellID."""
    with session_ctx() as session:
        found_well = (
            session.query(Thing)
            .filter(Thing.nma_pk_welldata == context.test_well.nma_pk_welldata)
            .first()
        )
        assert found_well is not None, "Well should be findable by legacy WellID"
        assert found_well.id == context.test_well.id, "Found well should match original"


@then("the well can store its original NM_Aquifer LocationID")
def step_then_well_stores_locationid(context: Context):
    """Verify well can store legacy LocationID."""
    assert (
        context.test_well.nma_pk_location is not None
    ), "Well should store legacy LocationID"
    assert isinstance(
        context.test_well.nma_pk_location, str
    ), "LocationID should be a string"


@then("the well can be found by its legacy LocationID")
def step_then_find_by_locationid(context: Context):
    """Verify well can be queried by legacy LocationID."""
    with session_ctx() as session:
        found_well = (
            session.query(Thing)
            .filter(Thing.nma_pk_location == context.test_well.nma_pk_location)
            .first()
        )
        assert found_well is not None, "Well should be findable by legacy LocationID"
        assert found_well.id == context.test_well.id, "Found well should match original"


# ============================================================================
# Chemistry Sample Info
# ============================================================================


@when("I try to save chemistry sample information")
def step_when_save_chemistry(context: Context):
    """Attempt to save chemistry sample info without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            chemistry = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="TEST001",
                thing_id=None,  # No parent well
                collection_date=datetime.now(),
            )
            session.add(chemistry)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("a well must be specified")
def step_then_well_required(context: Context):
    """Verify that a well (thing_id) is required."""
    assert not context.record_saved, "Record should not be saved without a well"
    assert context.orphan_error is not None, "Should raise error when well is missing"


@then("orphaned chemistry records are not allowed")
def step_then_no_orphan_chemistry(context: Context):
    """Verify no orphan chemistry records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_Chemistry_SampleInfo)
            .filter(NMA_Chemistry_SampleInfo.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan chemistry records"


# ============================================================================
# Hydraulics Data
# ============================================================================


@when("I try to save hydraulic test data")
def step_when_save_hydraulics(context: Context):
    """Attempt to save hydraulic data without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            hydraulics = NMA_HydraulicsData(
                global_id=uuid.uuid4(),
                point_id="TEST001",
                thing_id=None,  # No parent well
                test_top=100,
                test_bottom=200,
            )
            session.add(hydraulics)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("orphaned hydraulic records are not allowed")
def step_then_no_orphan_hydraulics(context: Context):
    """Verify no orphan hydraulic records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_HydraulicsData)
            .filter(NMA_HydraulicsData.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan hydraulic records"


# ============================================================================
# NMA_Stratigraphy (Lithology)
# ============================================================================


@when("I try to save a lithology log")
def step_when_save_lithology(context: Context):
    """Attempt to save lithology log without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            stratigraphy = NMA_Stratigraphy(
                global_id=uuid.uuid4(),
                point_id="TEST001",
                thing_id=None,  # No parent well
                strat_top=100.0,
                strat_bottom=200.0,
            )
            session.add(stratigraphy)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("orphaned lithology records are not allowed")
def step_then_no_orphan_lithology(context: Context):
    """Verify no orphan lithology records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_Stratigraphy)
            .filter(NMA_Stratigraphy.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan lithology records"


# ============================================================================
# Radionuclides
# ============================================================================


@when("I try to save radionuclide results")
def step_when_save_radionuclides(context: Context):
    """Attempt to save radionuclide results without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            # First create a chemistry sample info for the radionuclide
            chemistry_sample = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="TEST001",
                thing_id=context.test_well_id,
                collection_date=datetime.now(),
            )
            session.add(chemistry_sample)
            session.flush()

            radionuclide = NMA_Radionuclides(
                global_id=uuid.uuid4(),
                thing_id=None,  # No parent well
                sample_pt_id=chemistry_sample.sample_pt_id,
                analyte="U-238",
            )
            session.add(radionuclide)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("orphaned radionuclide records are not allowed")
def step_then_no_orphan_radionuclides(context: Context):
    """Verify no orphan radionuclide records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_Radionuclides)
            .filter(NMA_Radionuclides.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan radionuclide records"


# ============================================================================
# Associated Data
# ============================================================================


@when("I try to save associated data")
def step_when_save_associated_data(context: Context):
    """Attempt to save associated data without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            associated_data = NMA_AssociatedData(
                assoc_id=uuid.uuid4(),
                point_id="TEST001",
                thing_id=None,  # No parent well
                notes="Test notes",
            )
            session.add(associated_data)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("orphaned associated data records are not allowed")
def step_then_no_orphan_associated_data(context: Context):
    """Verify no orphan associated data records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_AssociatedData)
            .filter(NMA_AssociatedData.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan associated data records"


# ============================================================================
# Soil/Rock Results
# ============================================================================


@when("I try to save soil or rock results")
def step_when_save_soil_rock(context: Context):
    """Attempt to save soil/rock results without a well."""
    context.orphan_error = None
    context.record_saved = False

    try:
        with session_ctx() as session:
            soil_rock = NMA_Soil_Rock_Results(
                point_id="TEST001",
                thing_id=None,  # No parent well
                sample_type="Soil",
                date_sampled="2025-01-01",
            )
            session.add(soil_rock)
            session.commit()
            context.record_saved = True
    except (ValueError, IntegrityError, StatementError) as e:
        context.orphan_error = e
        context.record_saved = False


@then("orphaned soil/rock records are not allowed")
def step_then_no_orphan_soil_rock(context: Context):
    """Verify no orphan soil/rock records exist."""
    with session_ctx() as session:
        orphan_count = (
            session.query(NMA_Soil_Rock_Results)
            .filter(NMA_Soil_Rock_Results.thing_id.is_(None))
            .count()
        )
        assert orphan_count == 0, f"Found {orphan_count} orphan soil/rock records"


# ============================================================================
# Relationship Navigation Tests
# ============================================================================


@when("I access the well's relationships")
def step_when_access_relationships(context: Context):
    """Access the well's relationships."""
    with session_ctx() as session:
        well = session.query(Thing).filter(Thing.id == context.test_well_id).first()
        context.well_relationships = {
            "chemistry_samples": well.chemistry_sample_infos,
            "hydraulics_data": well.hydraulics_data,
            "lithology_logs": well.stratigraphy_logs,
            "radionuclides": well.radionuclides,
            "associated_data": well.associated_data,
            "soil_rock_results": well.soil_rock_results,
        }


@then("I can navigate to all related record types")
def step_then_navigate_relationships(context: Context):
    """Verify all relationship types are accessible."""
    assert "chemistry_samples" in context.well_relationships
    assert "hydraulics_data" in context.well_relationships
    assert "lithology_logs" in context.well_relationships
    assert "radionuclides" in context.well_relationships
    assert "associated_data" in context.well_relationships
    assert "soil_rock_results" in context.well_relationships


@then("each relationship returns the correct records")
def step_then_relationships_correct(context: Context):
    """Verify each relationship returns the expected records."""
    assert len(context.well_relationships["chemistry_samples"]) >= 1
    assert len(context.well_relationships["hydraulics_data"]) >= 1
    assert len(context.well_relationships["lithology_logs"]) >= 1
    assert len(context.well_relationships["radionuclides"]) >= 1
    assert len(context.well_relationships["associated_data"]) >= 1
    assert len(context.well_relationships["soil_rock_results"]) >= 1


# ============================================================================
# Cascade Delete Tests
# ============================================================================


@given("a well has chemistry sample records")
def step_given_well_has_chemistry(context: Context):
    """Create chemistry samples for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        chemistry1 = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid.uuid4(),
            sample_point_id="TEST001",
            thing_id=context.test_well_id,
            collection_date=datetime.now(),
        )
        chemistry2 = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid.uuid4(),
            sample_point_id="TEST002",
            thing_id=context.test_well_id,
            collection_date=datetime.now(),
        )
        session.add_all([chemistry1, chemistry2])
        session.commit()
        context.chemistry_samples = [chemistry1, chemistry2]


@given("a well has hydraulic test data")
def step_given_well_has_hydraulics(context: Context):
    """Create hydraulic data for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        hydraulics = NMA_HydraulicsData(
            global_id=uuid.uuid4(),
            point_id="TEST001",
            thing_id=context.test_well_id,
            test_top=100,
            test_bottom=200,
        )
        session.add(hydraulics)
        session.commit()
        context.hydraulics_data = hydraulics


@given("a well has lithology logs")
def step_given_well_has_lithology(context: Context):
    """Create lithology logs for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        lithology1 = NMA_Stratigraphy(
            global_id=uuid.uuid4(),
            point_id="TEST001",
            thing_id=context.test_well_id,
            strat_top=0.0,
            strat_bottom=100.0,
        )
        lithology2 = NMA_Stratigraphy(
            global_id=uuid.uuid4(),
            point_id="TEST001",
            thing_id=context.test_well_id,
            strat_top=100.0,
            strat_bottom=200.0,
        )
        session.add_all([lithology1, lithology2])
        session.commit()
        context.lithology_logs = [lithology1, lithology2]


@given("a well has radionuclide results")
def step_given_well_has_radionuclides(context: Context):
    """Create radionuclide results for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        chemistry_sample = NMA_Chemistry_SampleInfo(
            sample_pt_id=uuid.uuid4(),
            sample_point_id="TEST001",
            thing_id=context.test_well_id,
            collection_date=datetime.now(),
        )
        session.add(chemistry_sample)
        session.flush()

        radionuclide = NMA_Radionuclides(
            global_id=uuid.uuid4(),
            thing_id=context.test_well_id,
            sample_pt_id=chemistry_sample.sample_pt_id,
            analyte="U-238",
        )
        session.add(radionuclide)
        session.commit()
        context.radionuclide_results = radionuclide


@given("a well has associated data")
def step_given_well_has_associated_data(context: Context):
    """Create associated data for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        associated_data = NMA_AssociatedData(
            assoc_id=uuid.uuid4(),
            point_id="TEST001",
            thing_id=context.test_well_id,
            notes="Test associated data",
        )
        session.add(associated_data)
        session.commit()
        context.associated_data = associated_data


@given("a well has soil and rock results")
def step_given_well_has_soil_rock(context: Context):
    """Create soil/rock results for a well."""
    if not hasattr(context, "test_well"):
        step_given_well_exists(context)

    with session_ctx() as session:
        soil_rock = NMA_Soil_Rock_Results(
            point_id="TEST001",
            thing_id=context.test_well_id,
            sample_type="Soil",
            date_sampled="2025-01-01",
        )
        session.add(soil_rock)
        session.commit()
        context.soil_rock_results = soil_rock


@when("the well is deleted")
def step_when_well_deleted(context: Context):
    """Delete the test well."""
    with session_ctx() as session:
        well = session.query(Thing).filter(Thing.id == context.test_well_id).first()
        if well:
            session.delete(well)
            session.commit()
        context.well_deleted = True


@then("its chemistry samples are also deleted")
def step_then_chemistry_deleted(context: Context):
    """Verify chemistry samples are cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_Chemistry_SampleInfo)
            .filter(NMA_Chemistry_SampleInfo.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 chemistry samples, found {remaining}"


@then("its hydraulic data is also deleted")
def step_then_hydraulics_deleted(context: Context):
    """Verify hydraulic data is cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_HydraulicsData)
            .filter(NMA_HydraulicsData.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 hydraulic records, found {remaining}"


@then("its lithology logs are also deleted")
def step_then_lithology_deleted(context: Context):
    """Verify lithology logs are cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_Stratigraphy)
            .filter(NMA_Stratigraphy.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 lithology logs, found {remaining}"


@then("its radionuclide results are also deleted")
def step_then_radionuclides_deleted(context: Context):
    """Verify radionuclide results are cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_Radionuclides)
            .filter(NMA_Radionuclides.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 radionuclide records, found {remaining}"


@then("its associated data is also deleted")
def step_then_associated_data_deleted(context: Context):
    """Verify associated data is cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_AssociatedData)
            .filter(NMA_AssociatedData.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 associated data records, found {remaining}"


@then("its soil/rock results are also deleted")
def step_then_soil_rock_deleted(context: Context):
    """Verify soil/rock results are cascade deleted."""
    with session_ctx() as session:
        remaining = (
            session.query(NMA_Soil_Rock_Results)
            .filter(NMA_Soil_Rock_Results.thing_id == context.test_well_id)
            .count()
        )
        assert remaining == 0, f"Expected 0 soil/rock records, found {remaining}"


# ============= EOF =============================================
