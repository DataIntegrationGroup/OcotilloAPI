Feature: Recall and share well information in the field
  As a field technician
  I want to recall information about a well while in the field
  And share a link with the well owner
  So that I can provide them with details and measurements such as a hydrograph

  Background:
    Given I am logged in as a field technician
    And I am using the Ocotillo mobile web UI in the field

  # --- Happy Path ---

  Scenario: Recall well details in the field
    Given I search for well ID "NM-123"
    When I open the well record
    Then I should see details including the well owner, construction information, and location
    And I should see a hydrograph of historical water level measurements

  Scenario: Share well details with the owner
    Given I am viewing the well record for well ID "NM-123"
    When I choose to share the well details
    Then the system should generate a shareable link
    And the link should display the well’s details and hydrograph when accessed
    And the link should be accessible without login for the well owner

  # --- Display & Content ---

  Scenario: Display well construction information
    Given I open a well record with construction details
    Then I should see casing diameter, depth, screen intervals, and well purpose if available

  Scenario: Display hydrograph in well record
    Given the well has historical water level measurements
    When I view the well record
    Then I should see a hydrograph with manual and continuous measurements clearly identified

  # --- Edge Cases ---

  Scenario: Well record not found
    Given I search for well ID "NM-9999" that does not exist
    When I attempt to open the well record
    Then I should see an error message indicating the well cannot be found

  Scenario: Well with no water level data
    Given I open a well record with no water level measurements
    Then I should see well details
    And a message stating that no hydrograph data is available

  Scenario: Link access permissions
    Given I share a well record link with the owner
    When someone else tries to access the link
    Then the system should require permission or deny access
    And only the intended well owner should be able to view the shared details

  Scenario: Expiring shared links
    Given I share a well record link with the owner
    When the link expires after 30 days
    Then the link should no longer be accessible
    And the system should prompt the field technician to generate a new link if needed

  Scenario: Offline access to well information
    Given I am in an area with no connectivity
    When I open a well record that was synced to my device earlier
    Then I should still be able to view the well details and most recent water level data
    And I should be notified that sharing links is unavailable offline
