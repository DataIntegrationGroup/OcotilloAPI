# Created by marissa at 12/11/2025
# file: tests/features/data_visibility_and_review_backend.feature

@backend @BDMS-XXX
Feature: Manage data visibility separately from review and approval in the backend
  As an Ocotillo data manager
  I want visibility/privacy and review/approval to be stored as two separate backend attributes
  So that the system can independently control who can see the data and which data is reviewed

  # Business rules:
  # - visibility has two states: "internal" or "public"
  # - review_status has two states: "provisional" or "approved"
  # - visibility and review_status are REQUIRED when creating new data
  # - new data must use visibility and review_status (no new use of legacy fields)
  # - legacy combined values will be migrated into visibility and review_status using a documented mapping

  Background:
    Given a functioning api
    And all database models have a visibility field that supports "internal" and "public"
    And all database models have a review_status field that supports "provisional" and "approved"
    And visibility and review_status are required fields when creating new records
    # hard to test?
    And new records must use visibility and review_status as the source of truth
    And legacy combined visibility/review fields are deprecated


  Scenario Outline: Require visibility and review status when creating a new record
    When I create a new <model> without specifying visibility or review_status
    Then the system should return a validation error status code (such as 400)
    And the system should not persist the new dataset
    And the error response should indicate that visibility is required
    And the error response should indicate that review_status is required

    # Given Require visibility and review status when creating a new record. no default for visibility and review
      # status will be defined so this is impossible to test
    And the error response should not include default values for visibility or review_status

    Examples:
    |model|
    |Well |
    |Contact|
    |Observation|

  Scenario Outline: Migrate legacy combined visibility/review values to separate fields
    Given the system has legacy records with a combined visibility/review field for <legacy_table>
    And there is a documented mapping from each legacy value to a visibility and review_status pair
    When the migration job runs to populate visibility and review_status for <legacy_table> records
    Then the system should set visibility according to the documented mapping
    And the system should set review_status according to the documented mapping
    # hard to test?
    And the system should stop using the legacy combined field as the source of truth
    And subsequent updates to migrated records should modify visibility and review_status fields only

    Examples:
    |legacy_table|
    |Location    |
    |WaterLevels |
    |WaterLevelsContinuous_Acoustic|
    |WaterLevelsContinuous_Pressure|

  Scenario: Spot-check migrated legacy records against the documented mapping
    Given the migration job has completed
    And the tester selects a sample of migrated records with known legacy values
    When the tester retrieves each sampled record via the api
    Then the visibility value for each sampled record should match the expected mapped visibility
    And the review_status value for each sampled record should match the expected mapped review_status

#
#  @skip
#  @patch
#  Scenario: Update visibility for a new dataset without changing review status
#    Given the system has a new dataset with visibility "internal" and review_status "provisional"
#    When the user updates the dataset visibility to "public" via the api
#    Then the system should persist the dataset with visibility "public"
#    And the system should preserve the review_status as "provisional"
#    And retrieving the dataset via the api should return visibility "public" and review_status "provisional"
#
#  @skip
#  @patch
#  Scenario: Update review status for a new dataset without changing visibility
#    Given the system has a new dataset with visibility "internal" and review_status "provisional"
#    When an authorized reviewer updates the dataset review_status to "approved" via the api
#    Then the system should persist the dataset with review_status "approved"
#    And the system should preserve the visibility as "internal"
#    And retrieving the dataset via the api should return visibility "internal" and review_status "approved"
#
#  @skip
#  @authorization
#  Scenario: Allow all datasets for internal users
#    Given the system has datasets with combinations of:
#      | visibility | review_status |
#      | internal   | provisional   |
#      | internal   | approved      |
#      | public     | provisional   |
#      | public     | approved      |
#    And the caller is identified as an internal staff user
#    When the internal staff user requests those datasets via the api
#    Then the system should return all of those datasets in the response
#
#  @skip @authorization
#  Scenario: Reject unauthorized changes to visibility or review status
#    Given the system has a dataset with visibility "internal" and review_status "provisional"
#    And the caller is authenticated without permission to change visibility or review_status
#    When the caller attempts to update the visibility to "public" via the api
#    And the caller attempts to update the review_status to "approved" via the api
#    Then the system should return an authorization error for these updates
#    And the dataset should remain persisted with visibility "internal" and review_status "provisional"
#
#  @skip
#  @disclaimer
#  Scenario: Include disclaimer information based on review status
#    Given the system has a dataset with visibility "public" and review_status "provisional"
#    When any authorized caller retrieves the dataset via the api
#    Then the system should return a response in JSON format
#    And the response should include a disclaimer field derived from the review_status
#    And the disclaimer should indicate that the data is provisional
#
#    And the system has a dataset with visibility "internal" and review_status "approved"
#    When any authorized caller retrieves that dataset via the api
#    Then the response should include a disclaimer field derived from the review_status
#    And the disclaimer should indicate that the data is approved
#
