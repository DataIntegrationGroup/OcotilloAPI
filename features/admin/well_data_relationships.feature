@data-integrity
Feature: Well Data Relationships
  As a NMBGMR data manager
  I need well-related records to always belong to a well
  So that data integrity is maintained and orphaned records are prevented

  Background:
    Given the Ocotillo database is set up

  # ============================================================================
  # Wells Store Legacy Identifiers
  # ============================================================================

  @wells
  Scenario: Wells store their legacy WellID
    Given a well record exists
    Then the well can store its original NM_Aquifer WellID
    And the well can be found by its legacy WellID

  @wells
  Scenario: Wells store their legacy LocationID
    Given a well record exists
    Then the well can store its original NM_Aquifer LocationID
    And the well can be found by its legacy LocationID

  # ============================================================================
  # Related Records Require a Well
  # ============================================================================

  @chemistry
  Scenario: Chemistry samples require a well
    When I try to save chemistry sample information
    Then a well must be specified
    And orphaned chemistry records are not allowed

  @hydraulics
  Scenario: Hydraulic test data requires a well
    When I try to save hydraulic test data
    Then a well must be specified
    And orphaned hydraulic records are not allowed

  @stratigraphy
  Scenario: Lithology logs require a well
    When I try to save a lithology log
    Then a well must be specified
    And orphaned lithology records are not allowed

  @radionuclides
  Scenario: Radionuclide results require a well
    When I try to save radionuclide results
    Then a well must be specified
    And orphaned radionuclide records are not allowed

  @associated-data
  Scenario: Associated data requires a well
    When I try to save associated data
    Then a well must be specified
    And orphaned associated data records are not allowed

  @soil-rock
  Scenario: Soil and rock results require a well
    When I try to save soil or rock results
    Then a well must be specified
    And orphaned soil/rock records are not allowed

  # ============================================================================
  # Deleting a Well Removes Related Records
  # ============================================================================

  @cascade-delete
  Scenario: Deleting a well removes its chemistry samples
    Given a well has chemistry sample records
    When the well is deleted
    Then its chemistry samples are also deleted

  @cascade-delete
  Scenario: Deleting a well removes its hydraulic data
    Given a well has hydraulic test data
    When the well is deleted
    Then its hydraulic data is also deleted

  @cascade-delete
  Scenario: Deleting a well removes its lithology logs
    Given a well has lithology logs
    When the well is deleted
    Then its lithology logs are also deleted

  @cascade-delete
  Scenario: Deleting a well removes its radionuclide results
    Given a well has radionuclide results
    When the well is deleted
    Then its radionuclide results are also deleted

  @cascade-delete
  Scenario: Deleting a well removes its associated data
    Given a well has associated data
    When the well is deleted
    Then its associated data is also deleted

  @cascade-delete
  Scenario: Deleting a well removes its soil/rock results
    Given a well has soil and rock results
    When the well is deleted
    Then its soil/rock results are also deleted
