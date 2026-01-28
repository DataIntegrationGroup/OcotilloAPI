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
Integration tests for Well Data Relationships feature.

These tests verify the business requirements from:
    features/admin/well_data_relationships.feature

Feature: Well Data Relationships
    As a NMBGMR data manager
    I need well-related records to always belong to a well
    So that data integrity is maintained and orphaned records are prevented
"""

import uuid

import pytest

from db.engine import session_ctx
from db.nma_legacy import (
    NMA_AssociatedData,
    NMA_Chemistry_SampleInfo,
    NMA_HydraulicsData,
    NMA_Radionuclides,
    NMA_Soil_Rock_Results,
    NMA_Stratigraphy,
)
from db.thing import Thing

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def well_for_relationships():
    """Create a well specifically for relationship testing."""
    with session_ctx() as session:
        well = Thing(
            name="FK Test Well",
            thing_type="water well",
            release_status="draft",
            nma_pk_welldata="TEST-WELLDATA-GUID-12345",
            nma_pk_location="TEST-LOCATION-GUID-67890",
        )
        session.add(well)
        session.commit()
        session.refresh(well)
        yield well
        # Cleanup: delete the well (should cascade to children)
        session.delete(well)
        session.commit()


# =============================================================================
# Wells Store Legacy Identifiers
# =============================================================================


class TestWellsStoreLegacyIdentifiers:
    """
    @wells
    Scenario: Wells store their legacy WellID
    Scenario: Wells store their legacy LocationID
    """

    def test_well_stores_legacy_welldata_id(self):
        """Wells can store their original NM_Aquifer WellID."""
        with session_ctx() as session:
            well = Thing(
                name="Legacy WellID Test",
                thing_type="water well",
                release_status="draft",
                nma_pk_welldata="LEGACY-WELLID-12345",
            )
            session.add(well)
            session.commit()
            session.refresh(well)

            assert well.nma_pk_welldata == "LEGACY-WELLID-12345"

            # Cleanup
            session.delete(well)
            session.commit()

    def test_well_found_by_legacy_welldata_id(self):
        """Wells can be found by their legacy WellID."""
        legacy_id = f"FINDME-WELL-{uuid.uuid4().hex[:8]}"
        with session_ctx() as session:
            well = Thing(
                name="Findable Well",
                thing_type="water well",
                release_status="draft",
                nma_pk_welldata=legacy_id,
            )
            session.add(well)
            session.commit()

            # Query by legacy ID
            found = (
                session.query(Thing).filter(Thing.nma_pk_welldata == legacy_id).first()
            )
            assert found is not None
            assert found.name == "Findable Well"

            session.delete(well)
            session.commit()

    def test_well_stores_legacy_location_id(self):
        """Wells can store their original NM_Aquifer LocationID."""
        with session_ctx() as session:
            well = Thing(
                name="Legacy LocationID Test",
                thing_type="water well",
                release_status="draft",
                nma_pk_location="LEGACY-LOCATIONID-67890",
            )
            session.add(well)
            session.commit()
            session.refresh(well)

            assert well.nma_pk_location == "LEGACY-LOCATIONID-67890"

            # Cleanup
            session.delete(well)
            session.commit()

    def test_well_found_by_legacy_location_id(self):
        """Wells can be found by their legacy LocationID."""
        legacy_id = f"FINDME-LOC-{uuid.uuid4().hex[:8]}"
        with session_ctx() as session:
            well = Thing(
                name="Findable by Location",
                thing_type="water well",
                release_status="draft",
                nma_pk_location=legacy_id,
            )
            session.add(well)
            session.commit()

            # Query by legacy ID
            found = (
                session.query(Thing).filter(Thing.nma_pk_location == legacy_id).first()
            )
            assert found is not None
            assert found.name == "Findable by Location"

            session.delete(well)
            session.commit()


# =============================================================================
# Related Records Require a Well
# =============================================================================


class TestRelatedRecordsRequireWell:
    """
    @chemistry, @hydraulics, @stratigraphy, @radionuclides, @associated-data, @soil-rock
    Scenarios: Various record types require a well (thing_id cannot be None)
    """

    def test_chemistry_sample_requires_well(self):
        """
        @chemistry
        Scenario: Chemistry samples require a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_Chemistry_SampleInfo(
                    sample_pt_id=uuid.uuid4(),
                    sample_point_id="ORPHAN-CHEM",
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()

    def test_hydraulics_data_requires_well(self):
        """
        @hydraulics
        Scenario: Hydraulic test data requires a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_HydraulicsData(
                    global_id=uuid.uuid4(),
                    point_id="ORPHANHYD",
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()

    def test_stratigraphy_requires_well(self):
        """
        @stratigraphy
        Scenario: Lithology logs require a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_Stratigraphy(
                    global_id=uuid.uuid4(),
                    point_id="ORPHSTRAT",
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()

    def test_radionuclides_requires_well(self):
        """
        @radionuclides
        Scenario: Radionuclide results require a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_Radionuclides(
                    sample_pt_id=uuid.uuid4(),
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()

    def test_associated_data_requires_well(self):
        """
        @associated-data
        Scenario: Associated data requires a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_AssociatedData(
                    point_id="ORPHAN-ASSOC",
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()

    def test_soil_rock_results_requires_well(self):
        """
        @soil-rock
        Scenario: Soil and rock results require a well
        """
        with session_ctx() as session:
            with pytest.raises(ValueError, match="requires a parent Thing"):
                record = NMA_Soil_Rock_Results(
                    point_id="ORPHAN-SOIL",
                    thing_id=None,  # This should raise ValueError
                )
                session.add(record)
                session.flush()


# =============================================================================
# Relationship Navigation
# =============================================================================


class TestRelationshipNavigation:
    """
    @relationships
    Scenario: A well can access its related records through relationships
    """

    def test_well_navigates_to_chemistry_samples(self, well_for_relationships):
        """Well can navigate to its chemistry sample records."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create a chemistry sample for this well
            sample = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="NAVCHEM01",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(sample)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "chemistry_sample_infos")
            assert len(well.chemistry_sample_infos) >= 1
            assert any(
                s.sample_point_id == "NAVCHEM01" for s in well.chemistry_sample_infos
            )

    def test_well_navigates_to_hydraulics_data(self, well_for_relationships):
        """Well can navigate to its hydraulic test data."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create hydraulics data for this well
            hydraulics = NMA_HydraulicsData(
                global_id=uuid.uuid4(),
                point_id="NAVHYD01",  # Max 10 chars
                thing_id=well.id,
                test_top=0,
                test_bottom=100,
            )
            session.add(hydraulics)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "hydraulics_data")
            assert len(well.hydraulics_data) >= 1
            assert any(h.point_id == "NAVHYD01" for h in well.hydraulics_data)

    def test_well_navigates_to_stratigraphy_logs(self, well_for_relationships):
        """Well can navigate to its lithology logs."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create stratigraphy log for this well
            strat = NMA_Stratigraphy(
                global_id=uuid.uuid4(),
                point_id="NAVSTRAT1",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(strat)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "stratigraphy_logs")
            assert len(well.stratigraphy_logs) >= 1
            assert any(s.point_id == "NAVSTRAT1" for s in well.stratigraphy_logs)

    def test_well_navigates_to_radionuclides(self, well_for_relationships):
        """Well can navigate to its radionuclide results."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create a chemistry sample for this well to satisfy the FK
            chem_sample = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="NAVRAD01",  # Required, max 10 chars
                thing_id=well.id,
            )
            session.add(chem_sample)
            session.flush()

            # Create radionuclide record for this well using the same sample_pt_id
            radio = NMA_Radionuclides(
                global_id=uuid.uuid4(),
                sample_pt_id=chem_sample.sample_pt_id,
                thing_id=well.id,
            )
            session.add(radio)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "radionuclides")
            assert len(well.radionuclides) >= 1

    def test_well_navigates_to_associated_data(self, well_for_relationships):
        """Well can navigate to its associated data."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create associated data for this well
            assoc = NMA_AssociatedData(
                assoc_id=uuid.uuid4(),
                point_id="NAVASSOC1",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(assoc)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "associated_data")
            assert len(well.associated_data) >= 1
            assert any(a.point_id == "NAVASSOC1" for a in well.associated_data)

    def test_well_navigates_to_soil_rock_results(self, well_for_relationships):
        """Well can navigate to its soil/rock results."""
        with session_ctx() as session:
            well = session.merge(well_for_relationships)

            # Create soil/rock result for this well
            soil = NMA_Soil_Rock_Results(
                point_id="NAV-SOIL-01",
                thing_id=well.id,
            )
            session.add(soil)
            session.commit()
            session.refresh(well)

            # Navigate through relationship
            assert hasattr(well, "soil_rock_results")
            assert len(well.soil_rock_results) >= 1
            assert any(s.point_id == "NAV-SOIL-01" for s in well.soil_rock_results)


# =============================================================================
# Deleting a Well Removes Related Records (Cascade Delete)
# =============================================================================


class TestCascadeDelete:
    """
    @cascade-delete
    Scenarios: Deleting a well removes its related records
    """

    def test_deleting_well_cascades_to_chemistry_samples(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its chemistry samples
        """
        with session_ctx() as session:
            # Create well with chemistry sample
            well = Thing(
                name="Cascade Chemistry Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            sample = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="CASCCHEM1",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(sample)
            session.commit()
            sample_id = sample.sample_pt_id  # PK is sample_pt_id

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify chemistry sample was also deleted
            orphan = session.get(NMA_Chemistry_SampleInfo, sample_id)
            assert orphan is None, "Chemistry sample should be deleted with well"

    def test_deleting_well_cascades_to_hydraulics_data(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its hydraulic data
        """
        with session_ctx() as session:
            # Create well with hydraulics data
            well = Thing(
                name="Cascade Hydraulics Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            hyd_global_id = uuid.uuid4()
            hydraulics = NMA_HydraulicsData(
                global_id=hyd_global_id,
                point_id="CASCHYD01",  # Max 10 chars
                thing_id=well.id,
                test_top=0,
                test_bottom=100,
            )
            session.add(hydraulics)
            session.commit()

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify hydraulics data was also deleted
            orphan = session.get(NMA_HydraulicsData, hyd_global_id)
            assert orphan is None, "Hydraulics data should be deleted with well"

    def test_deleting_well_cascades_to_stratigraphy_logs(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its lithology logs
        """
        with session_ctx() as session:
            # Create well with stratigraphy log
            well = Thing(
                name="Cascade Stratigraphy Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            strat_global_id = uuid.uuid4()
            strat = NMA_Stratigraphy(
                global_id=strat_global_id,
                point_id="CASCSTRAT",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(strat)
            session.commit()

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify stratigraphy was also deleted
            orphan = session.get(NMA_Stratigraphy, strat_global_id)
            assert orphan is None, "Stratigraphy log should be deleted with well"

    def test_deleting_well_cascades_to_radionuclides(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its radionuclide results
        """
        with session_ctx() as session:
            # Create well with radionuclide record
            well = Thing(
                name="Cascade Radionuclides Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            # Create a chemistry sample for this well to satisfy the FK
            chem_sample = NMA_Chemistry_SampleInfo(
                sample_pt_id=uuid.uuid4(),
                sample_point_id="CASCRAD01",  # Required, max 10 chars
                thing_id=well.id,
            )
            session.add(chem_sample)
            session.flush()

            # Create radionuclide record using the chemistry sample's sample_pt_id
            radio = NMA_Radionuclides(
                global_id=uuid.uuid4(),
                sample_pt_id=chem_sample.sample_pt_id,
                thing_id=well.id,
            )
            session.add(radio)
            session.commit()
            radio_id = radio.global_id  # PK is global_id

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify radionuclide record was also deleted
            orphan = session.get(NMA_Radionuclides, radio_id)
            assert orphan is None, "Radionuclide record should be deleted with well"

    def test_deleting_well_cascades_to_associated_data(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its associated data
        """
        with session_ctx() as session:
            # Create well with associated data
            well = Thing(
                name="Cascade Associated Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            assoc_uuid = uuid.uuid4()
            assoc = NMA_AssociatedData(
                assoc_id=assoc_uuid,
                point_id="CASCASSOC",  # Max 10 chars
                thing_id=well.id,
            )
            session.add(assoc)
            session.commit()

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify associated data was also deleted
            orphan = session.get(NMA_AssociatedData, assoc_uuid)
            assert orphan is None, "Associated data should be deleted with well"

    def test_deleting_well_cascades_to_soil_rock_results(self):
        """
        @cascade-delete
        Scenario: Deleting a well removes its soil/rock results
        """
        with session_ctx() as session:
            # Create well with soil/rock results
            well = Thing(
                name="Cascade Soil Rock Test",
                thing_type="water well",
                release_status="draft",
            )
            session.add(well)
            session.commit()

            soil = NMA_Soil_Rock_Results(
                point_id="CASCSOIL1",
                thing_id=well.id,
            )
            session.add(soil)
            session.commit()
            soil_id = soil.id

            # Delete the well
            session.delete(well)
            session.commit()

            # Clear session cache to ensure fresh DB query
            session.expire_all()

            # Verify soil/rock results were also deleted
            orphan = session.get(NMA_Soil_Rock_Results, soil_id)
            assert orphan is None, "Soil/rock results should be deleted with well"
