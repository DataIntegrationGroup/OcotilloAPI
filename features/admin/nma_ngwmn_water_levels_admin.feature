@admin @ngwmn-water-levels
Feature: NGWMN Water Levels Admin View
  As a data manager who needs legacy NGWMN water level records
  I need to view NGWMN water levels in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View NGWMN water levels list with all columns
    Given the following NGWMN water level records exist:
      | point_id | date_measured | depth_to_water_bgs | wl_units |
      | NG-0002  | 2020-05-20    | 35.5               | ft       |
    When I navigate to "/admin/ngwmnwaterlevels"
    Then I should see the NGWMN water levels list page
    And I should see the following columns:
      | Column Name         |
      | PointID             |
      | DateMeasured        |
      | DepthToWaterBGS     |
      | WLUnits             |
      | MeasurementMethod   |
      | WLAccuracy          |
      | PublicRelease       |
