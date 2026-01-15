@admin @radionuclides
Feature: Radionuclides Admin View
  As a data manager who needs legacy radionuclide records
  I need to view radionuclides in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View radionuclides list with all columns
    Given the following radionuclide records exist:
      | global_id                            | sample_pt_id                         | sample_point_id | thing_id | analyte | sample_value | units | analysis_date |
      | 0b94060d-11b8-4e43-bc3b-4e3a5c1e9f2a | 550e8400-e29b-41d4-a716-446655440001 | NM-0002         | 2        | U-238   | 0.12         | pCi/L | 2020-06-22    |
    When I navigate to "/admin/radionuclides"
    Then I should see the radionuclides list page
    And I should see the following columns:
      | Column Name      |
      | GlobalID         |
      | SamplePtID       |
      | SamplePointID    |
      | Thing ID         |
      | Analyte          |
      | SampleValue      |
      | Units            |
      | AnalysisDate     |
      | AnalysesAgency   |
