@admin @weather-data
Feature: Weather Data Admin View
  As a data manager who needs legacy weather records
  I need to view weather data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View weather data list with all columns
    Given the following weather data records exist:
      | object_id | point_id | location_id                         | weather_id                          |
      | 201       | WX-0001  | 550e8400-e29b-41d4-a716-446655440010 | 550e8400-e29b-41d4-a716-446655440011 |
    When I navigate to "/admin/weatherdata"
    Then I should see the weather data list page
    And I should see the following columns:
      | Column Name |
      | LocationId  |
      | PointID     |
      | WeatherID   |
      | OBJECTID    |
