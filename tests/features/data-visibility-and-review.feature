# Created by marissa at 12/11/2025
# file: tests/features/data_visibility_and_review_backend.feature

@backend @BDMS-XXX
Feature: Manage data visibility separately from review in the backend
  As an Ocotillo data manager
  I want visibility and review status to be stored as two separate backend attributes
  So that the system can independently control who can see the data and which data is reviewed

  # Business rules:
  # - visibility has two states: "internal" or "public"
  # - review_status has two states: "provisional" or "approved"
  # - visibility and review_status are REQUIRED when creating new data
  # - new data must use visibility and review_status (no new use of legacy fields)
  # - legacy combined values will be migrated into visibility and review_status using a documented mapping
  # - visibility and review must cover previous release_status business logic

  Background:
    Given a functioning api
    And all database models have a visibility field that determines if a record can or cannot be viewed by the public
    And the only possible values for the visibility field are internal and public
    And all database models have a review_status field that determines if a record is provisional or approved
    And the only possible values for the review_status field are provisional and approved
    And visibility and review_status are required fields when creating new records
    And new records must use visibility and review_status as the source of truth
    And legacy combined visibility/review fields are deprecated

  # ---------------------------------------------------------------------------
  # PUBLIC ACCESS
  # ---------------------------------------------------------------------------

  @public_access @visibility
  Scenario Outline: Public users can only access public data
    Given I am a public API consumer
    And there is <data_type> data stored with a visibility field that evaluates to either public or internal
    When I request <data_type> data through API endpoints
    Then I should only see records where the visibility field is set to public
    And records whose visibility field is set to internal should not be returned
    And the response should include the review_status for each public record

    Examples:
      | data_type    |
      | locations    |
      | samples      |
      | observations |

  # might not be relevant yet in NMSampleLocations
  @public_access @reports
  Scenario: Public reports include review status disclaimers
    Given a am a public API consumer
    And data is stored with visibility public and review_status provisional or approved
    When I request a report of observations
    Then all returned observations should have visibility public
    And provisional observations should include a disclaimer derived from review_status
    And approved observations should indicate that they are fully reviewed

  # might not be relevant yet in NMSampleLocations
  @public_access @data_download
  Scenario: Public data downloads exclude internal datasets
    Given I am a public API consumer
    And the data contains public and internal records with different review_status values
    When I requests a CSV export
    Then only the public records should be included
    And the download should list the review_status for each record

  # ---------------------------------------------------------------------------
  # AUTHENTICATED STAFF ACCESS
  # ---------------------------------------------------------------------------

  @staff_access @visibility
  Scenario Outline: Staff can access all data and its review status
    Given I am an authenticated staff member
    And I have permission to view internal data
    When I view <data_type> data through API endpoints
    Then I should see visibility internal and public records
    And I should see whether each record is provisional or approved

    Examples:
      | data_type    |
      | things       |
      | locations    |
      | samples      |
      | observations |

  @staff_access @management
  Scenario: Staff can change visibility without affecting review status
    Given I am an authenticated staff member
    And I have permission to modify data visibility
    And data is stored with visibility internal and review_status provisional
    When I update the visibility to public
    Then the data visibility should be persisted as public
    And the review_status should remain provisional
    And retrieving the data should show the updated visibility and original review_status

  @staff_access @review_status
  Scenario: Staff can approve data without changing visibility
    Given I am an authenticated staff member
    And I have permission to modify data review status
    Given data is stored with visibility public and review_status provisional
    When I update the review_status to approved
    Then the data should remain visible to the public
    And the review_status should be persisted as approved
    And the API response should immediately show the approved status

  # ---------------------------------------------------------------------------
  # DATA SUBMISSION AND WORKFLOW
  # ---------------------------------------------------------------------------

  @workflow @validation
  Scenario Outline: New records require explicit visibility and review status
    When I attempt to create a new <data_type> without both visibility and review_status
    Then the request should be rejected with a 422 status code
    And the error response should indicate that visibility is required
    And the error response should indicate that review_status is required

    Examples:
      | data_type    |
      | thing        |
      | contact     |
      | observation |

  @workflow @defaults
  Scenario: Safe defaults when both attributes are omitted
    Given data is being submitted to the system with visibility and review_status omitted
    When the record is created
    Then the system should persist visibility internal and review_status provisional by default

  @workflow @privacy_protection
  Scenario: Contact data is private and protected by default
    Given private contact data is being submitted
    When the data is entered into the system
    Then the data should default to be stored with visibility internal
    And the data should default to be stored with review_status provisional
  
  # may need to work this out more
  # should we include the legacy table examples?
  @workflow @migration
  Scenario: Legacy combined values are migrated into separate attributes
    Given legacy records exist with a combined visibility/review field
    And a documented mapping defines visibility and review_status for each legacy value
    When the data transfer migration job runs
    Then each record should have visibility populated according to the mapping
    And each record should have review_status populated according to the mapping

  # ---------------------------------------------------------------------------
  # VISIBILITY AND REVIEW MANAGEMENT
  # ---------------------------------------------------------------------------

  @management @status_change
  Scenario: Making internal data public without re-review
    Given a <data_type> is currently visibility internal and review_status approved
    And appropriate authorization has been obtained
    When staff changes the visibility to public
    Then the <data_type> should become visible to unauthenticated users
    And the review_status should remain approved
    And associated observations should also reflect the new visibility

    Examples:
      | data_type    |
      | thing        |
      | location     |
      | sample       |

  @management @status_change
  Scenario: Moving public data back to internal without changing review status
    Given a thing is currently visibility public and review_status approved
    And a data owner requests privacy
    When staff changes the visibility to internal
    Then the thing should disappear from public endpoints
    And the review_status should continue to show approved
    And all associated data should remain approved but hidden

  @management @bulk_operations
  Scenario: Bulk updates keep visibility and review_status in sync
    Given a project has 50 things with visibility internal and review_status provisional
    And the project has completed internal review
    When staff performs a bulk change to set visibility public and review_status approved
    Then all 50 things should become publicly visible
    And all 50 things should show review_status approved

  # ---------------------------------------------------------------------------
  # DATA INTEGRITY AND CONSISTENCY
  # ---------------------------------------------------------------------------

  @integrity @cascading
  Scenario: Visibility restrictions cascade to associated data
    Given an internal thing has observations and samples
    When a public user queries for data
    Then all data associated with that thing should be hidden
    And no review_status values for those internal records should be exposed

  @integrity @mixed_status
  Scenario: Handling different review statuses for public data
    Given a thing is visibility public
    And individual observations at the thing have review_status provisional and approved
    When a public user views the thing data
    Then only observations with visibility public should appear
    And each observation should clearly display whether it is provisional or approved

  # ---------------------------------------------------------------------------
  # SPECIAL DATA REPRESENTATION
  # ---------------------------------------------------------------------------

  @special_cases @defaults
  Scenario: Certain data types default to public and provisional
    Given certain categories of data are configured to default to visibility public and review_status provisional
    When new data of these types is collected
    Then the data should be automatically marked as public
    And the review_status should be set to provisional until staff approval

  @special_cases @representation
  Scenario: Visibility and review status are consistently represented
    Given a record has visibility and review_status set
    When the data is viewed through any interface
    Then both fields should be clearly indicated
    And the public/private and provisional/approved statuses should be unambiguous
