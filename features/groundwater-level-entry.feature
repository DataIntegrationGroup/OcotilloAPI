Feature: Record groundwater level measurement in the field
  As a field technician
  I want a digital form to record all necessary information when measuring groundwater levels
  So that field data can be consistently collected and stored in the system

  Background:
    Given I am logged in as a field technician
    And I am at a well site with Ocotillo open on a mobile device

  # --- Happy Path ---

  Scenario: Record a groundwater level measurement with all required fields
    When I open the "New Measurement" form
    And I enter the well ID "NM-123"
    And I enter the date "2025-10-02" and time "09:30"
    And I enter the measured groundwater level "145.3"
    And I select the measurement method "Electric tape"
    And I enter my initials as the observer
    And I save the form
    Then the measurement should be stored in the system
    And the new record should appear in the well’s measurement history

  # --- Required Fields ---

  Scenario Outline: Required field validation
    When I open the "New Measurement" form
    And I leave the <field> blank
    And I attempt to save the form
    Then I should receive an error message indicating the <field> is required
    And the form should not be submitted

    Examples:
      | field               |
      | Well ID             |
      | Date                |
      | Time                |
      | Groundwater Level   |
      | Measurement Method  |
      | Observer Initials   |

  # --- Optional Fields ---

  Scenario Outline: Record optional field values
    When I open the "New Measurement" form
    And I enter a value in the <field> field: "<value>"
    And I save the form
    Then the <field> should be stored with the measurement record

    Examples:
      | field                | value                    |
      | Notes                | "Well cap was damaged"   |
      | Environmental Cond.  | "Rainy, muddy conditions"|
      | GPS Coordinates      | "34.051N, 106.892W"      |
      | Depth to Pump Intake | "60 ft"                  |

  # --- Value Validation ---

  Scenario: Invalid groundwater level value
    When I open the "New Measurement" form
    And I enter "ABC" in the groundwater level field
    And I attempt to save the form
    Then I should receive an error message indicating the groundwater level must be numeric
    And the form should not be submitted

  Scenario: Invalid date or time
    When I enter a future date "2050-01-01"
    And I attempt to save the form
    Then I should receive an error message indicating the date is invalid

  # --- Offline & Sync ---

  Scenario: Record measurement offline
    Given I have no connectivity
    When I fill out and save the "New Measurement" form
    Then the record should be stored locally on my device
    And when connectivity is restored
    Then the record should sync automatically to the system

  Scenario: Sync conflict resolution
    Given I record a measurement offline
    And another technician records a measurement for the same well and time online
    When my record syncs
    Then I should be notified of a conflict
    And I should have the option to review and resolve it before final submission
