@admin @water-levels-continuous-pressure-daily
Feature: Water Levels Continuous Pressure Daily Admin View
  As a data manager who needs legacy water level records
  I need to view continuous pressure daily water levels in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View continuous pressure daily water levels list with all columns
    Given the following continuous pressure daily water level records exist:
      | global_id                            | point_id | date_measured        | created              | updated              |
      | 7a3d2db5-0f3a-4e43-95b6-61b14f2a9cb2 | WL-0001  | 2020-06-15T08:00:00  | 2020-06-16T08:00:00  | 2020-06-17T08:00:00  |
    When I navigate to "/admin/waterlevelscontinuouspressuredaily"
    Then I should see the continuous pressure daily water levels list page
    And I should see the following columns:
      | Column Name            |
      | GlobalID               |
      | OBJECTID               |
      | WellID                 |
      | PointID                |
      | DateMeasured           |
      | TemperatureWater       |
      | WaterHead              |
      | WaterHeadAdjusted      |
      | DepthToWaterBGS        |
      | MeasurementMethod      |
      | DataSource             |
      | MeasuringAgency        |
      | QCed                   |
      | Notes                  |
      | Created                |
      | Updated                |
      | ProcessedBy            |
      | CheckedBy              |
      | CONDDL (mS/cm)         |
