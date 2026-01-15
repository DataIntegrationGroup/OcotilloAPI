@admin @major-chemistry
Feature: Major Chemistry Admin View
  As a data manager who needs legacy major chemistry records
  I need to view major chemistry data in the admin interface
  So that I can review data without editing it

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  @smoke @list-view
  Scenario: View major chemistry list with all columns
    Given the following major chemistry records exist:
      | global_id                            | sample_pt_id                         | sample_point_id | analyte | sample_value | units | analysis_date |
      | 9d3a2e2c-5b2b-4e1f-8a90-c1c79f1d9d11 | 550e8400-e29b-41d4-a716-446655440002 | NM-0003         | Ca      | 45.6         | mg/L  | 2020-06-25    |
    When I navigate to "/admin/majorchemistry"
    Then I should see the major chemistry list page
    And I should see the following columns:
      | Column Name      |
      | GlobalID         |
      | SamplePtID       |
      | SamplePointID    |
      | Analyte          |
      | Symbol           |
      | SampleValue      |
      | Units            |
      | Uncertainty      |
      | AnalysisMethod   |
      | AnalysisDate     |
      | Notes            |
      | Volume           |
      | VolumeUnit       |
      | OBJECTID         |
      | AnalysesAgency   |
      | WCLab_ID         |
