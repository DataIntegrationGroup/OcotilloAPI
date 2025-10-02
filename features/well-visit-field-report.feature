Feature: Generate a PDF report for a well visit
  As a field technician
  I want to generate a comprehensive PDF report of an existing well
  So that I have all necessary information before visiting for water level sampling

  Background:
    Given I am logged in as a field technician
    And a well with associated metadata and records exists in the system

  # --- Happy Path End-to-End ---

  Scenario: Generate a complete PDF report with all available information
    Given I request a PDF report for a well with full data available
    And the well has existing water level measurements
    And the well has notes about its condition and construction
    And the well has construction details including casing diameter, depth, screen intervals, and purpose
    And the well has associated owner and contact information
    And the well has directions recorded for site access
    And the well has photos of the well and its surroundings
    And the well has historical water level data for plotting
    When I generate the PDF report
    Then the report should include all water level measurements
    And the report should include notes about the well
    And the report should include full well construction details
    And the report should include owner and contact information
    And the report should include directions to the well
    And the report should include photos of the well and surroundings
    And the report should include a hydrograph of historical water levels
    And the report should be formatted in a clear, professional layout
    And the report should be downloadable and printable

  # --- Core Functionality Scenarios ---

  Scenario: Generate PDF report with core well information
    When I request a PDF report for a specific well
    Then the report should include existing water level measurements
    And the report should include notes about the well
    And the report should include well construction information such as casing diameter, depth, screen intervals, and purpose if available

  Scenario: Include hydrograph in the PDF report
    Given the well has historical water level data
    When I generate the PDF report
    Then a hydrograph of the well’s water levels should be included

  Scenario: Include directions to the well
    When I generate the PDF report
    Then the report should include directions to the well location

  Scenario: Include owner and contact information
    Given the well has associated owner and contacts
    When I generate the PDF report
    Then the report should include owner details
    And the report should include associated contact information such as property manager, farm hand, or others for access

  Scenario: Include photos of the well and surroundings
    Given photos of the well and its surroundings are stored in the system
    When I generate the PDF report
    Then the photos should be included in the report

  Scenario: Comprehensive formatting of PDF report
    When I generate the PDF report
    Then the report should be structured in a clear, professional layout
    And all included information should be organized into labeled sections
    And the report should be downloadable and printable

  # --- Edge Cases ---

  Scenario: Missing well construction data
    Given the well has no recorded construction information
    When I generate the PDF report
    Then the report should indicate that construction details are not available
    And the rest of the report should still be generated

  Scenario: Missing photos of the well
    Given no photos are stored for the well
    When I generate the PDF report
    Then the report should omit the photo section or mark it as unavailable
    And the rest of the report should still be complete

  Scenario: Missing owner or contact information
    Given the well has no associated owner or contact information
    When I generate the PDF report
    Then the report should indicate that contact details are not available
    And directions and other sections should still be included

  Scenario: Well with no water level history
    Given the well has no water level data
    When I generate the PDF report
    Then the report should not include a hydrograph
    And the report should state that no water level records are available

  Scenario: Offline or failed report generation
    Given the system is temporarily unavailable
    When I attempt to generate a PDF report
    Then I should receive an error message
    And the system should not produce a partial or corrupted PDF
