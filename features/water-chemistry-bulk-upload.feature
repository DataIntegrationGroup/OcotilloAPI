Feature: Upload spreadsheet of water chemistry data
  As a data manager
  I want to upload a spreadsheet of water chemistry data to the system via the web UI
  So that I can manage bulk data entry with proper validation and rollback

  Background:
    Given I am logged in as a data manager
    And I have access to the Ocotillo web UI

  # --- Happy Path ---

  Scenario: Successful upload of water chemistry spreadsheet
    Given I have a spreadsheet in the required format with valid water chemistry data
    When I upload the spreadsheet through the web UI
    Then the system should validate the file format
    And the data should be imported into the system
    And I should see the results displayed in a table
    And I should receive a confirmation that the upload was successful

  # --- File Format & Validation ---

  Scenario: Upload fails due to incorrect file format
    Given I have a spreadsheet in an unsupported format
    When I attempt to upload the file
    Then the system should reject the file
    And I should receive an error message describing the issue
    And no changes should be made to the system

  Scenario: Upload fails due to missing required fields
    Given I have a spreadsheet missing required columns (e.g., Sample ID or Date)
    When I attempt to upload the file
    Then the system should reject the upload
    And I should receive an error message listing the missing fields
    And no data should be imported

  Scenario: Upload fails due to invalid data
    Given I have a spreadsheet with invalid values (e.g., negative concentration)
    When I attempt to upload the file
    Then the system should reject the invalid rows
    And I should receive a validation report highlighting the errors
    And no invalid records should be imported

  # --- Rollback & Assurance ---

  Scenario: Rollback on partial failure
    Given I upload a spreadsheet with some valid and some invalid rows
    When the system processes the upload
    Then the entire upload should be rolled back
    And I should receive a message that no records were imported due to errors
    And I should be able to correct the spreadsheet and try again

  Scenario: Transaction log for uploads
    Given I successfully upload a spreadsheet of water chemistry data
    When I view the system activity log
    Then I should see an entry showing who uploaded the file, when, and how many records were added

  # --- User Feedback ---

  Scenario: Upload progress indicator
    When I upload a large spreadsheet
    Then I should see a progress indicator or spinner
    And I should be notified once the upload is complete

  Scenario: Preview uploaded data
    Given I upload a valid spreadsheet
    When the system parses the file
    Then I should see a preview of the first few rows
    And I should have an option to confirm before committing the data

  Scenario: Cancel upload
    Given I am in the process of uploading a spreadsheet
    When I cancel the upload
    Then no data should be imported
    And I should be returned to the upload screen
