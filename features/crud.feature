Feature: Manage records via Ocotillo web UI
  As a data manager
  I want full CRUD functionality in Ocotillo’s data system
  And the ability to export individual tables as CSV
  So that I can maintain and share groundwater data effectively

  Background:
    Given I am logged in as a data manager
    And a table named "Groundwater Levels" exists in the Ocotillo system

  # --- Happy Path End-to-End ---

  Scenario: Perform full CRUD workflow on records
    Given the "Groundwater Levels" table is empty
    When I create a new record with well ID "NM-001", timestamp "2025-10-02", and water level "145.2"
    And I update the record to correct the water level to "144.8"
    And I delete the record
    Then the table should be empty again
    And I should be able to export the table as a CSV file with only headers

  # --- Core CRUD Scenarios ---

  Scenario: Create a new record
    When I create a new record in "Groundwater Levels" with well ID "NM-002", timestamp "2025-09-30", and water level "152.5"
    Then the new record should appear in the "Groundwater Levels" table

  Scenario: Read and view records
    Given the "Groundwater Levels" table has multiple records
    When I open the table in the Ocotillo UI
    Then I should see all records with well IDs, timestamps, and water levels

  Scenario: Update a record
    Given the "Groundwater Levels" table has a record with well ID "NM-003"
    When I update the water level value in that record
    Then the updated value should be stored in the system
    And the change should be visible in the table

  Scenario: Delete a record
    Given the "Groundwater Levels" table has a record with well ID "NM-004"
    When I delete the record
    Then the record should no longer appear in the table

  # --- CSV Export Scenarios ---

  Scenario: Export a table as CSV
    Given the "Groundwater Levels" table has multiple records
    When I export the table as CSV
    Then I should receive a CSV file with all records and headers
    And the file should be downloadable

  # --- Edge Cases ---

  Scenario: Attempt to create a record with missing required fields
    When I create a new record without a well ID
    Then I should receive an error message
    And the record should not be saved

  Scenario: Update a record with invalid data
    Given the "Groundwater Levels" table has a record with well ID "NM-005"
    When I update the water level with a non-numeric value "ABC"
    Then the system should reject the update
    And the original value should remain unchanged

  Scenario: Export an empty table
    Given the "Groundwater Levels" table exists but has no records
    When I export the table as CSV
    Then I should receive a CSV file with only headers
    And no data rows

  Scenario: Export fails due to system error
    Given the "Groundwater Levels" table has records
    When I attempt to export the table as CSV during a system outage
    Then I should receive an error message
    And no corrupted file should be generated

  # --- Permissions & Roles ---

  Scenario: Data manager can create, update, and delete records
    Given I am logged in as a data manager
    When I create, update, and delete records in "Groundwater Levels"
    Then all actions should succeed
    And the changes should be saved in the system

  Scenario: Regular user can only view records
    Given I am logged in as a regular user
    When I open the "Groundwater Levels" table
    Then I should be able to view the records
    But I should not see options to create, update, or delete records

  Scenario: Read-only user can view and export tables
    Given I am logged in as a read-only user
    When I open the "Groundwater Levels" table
    Then I should be able to view the records
    And I should be able to export the table as CSV
    But I should not see options to create, update, or delete records

  Scenario: Unauthorized user cannot access data
    Given I am not logged in
    When I attempt to open the "Groundwater Levels" table
    Then I should be redirected to the login page
    And I should not be able to access the records
