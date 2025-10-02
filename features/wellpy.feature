Feature: Correcting groundwater level measurements using hydrograph visualization
  As a hydrogeologist and data manager
  I want to visualize, add, and adjust groundwater level data
  So that continuous transducer data can be referenced and corrected to manual measurements

  Background:
    Given I am logged in as myself and have the "HydrographEditor" permission
    And I have existing manual and continuous groundwater level data in the system

  Scenario: Display existing data on a hydrograph
    When I open the hydrograph view for a site
    Then I should see existing manual measurements clearly identified
    And I should see existing continuous measurements clearly identified

  Scenario: Add new continuous data to hydrograph
    Given I have uploaded new continuous groundwater level data
    When I open the hydrograph view
    Then I should see the new data displayed on the hydrograph
    And the new data should be clearly distinguished from the existing data

  Scenario: Snap sections of continuous data to manual reference measurements
    Given I have selected a section of new continuous data
    And I have corresponding manual measurements
    When I choose to snap the section to the manual reference
    Then the section should be adjusted to align with the manual measurements

  Scenario: Manually shift a section of the time series
    Given I have selected a section of the continuous data on the hydrograph
    When I manually shift the section up by X units
    Then the section should display adjusted values increased by X units
    When I manually shift the section down by Y units
    Then the section should display adjusted values decreased by Y units

  Scenario: Automatically identify systematically offset measurements
    Given I have continuous acoustic sensor data
    When the system analyzes the data for systematic offsets
    Then measurements that are consistently offset should be identified
    And the offsets should be flagged for review or automatic correction