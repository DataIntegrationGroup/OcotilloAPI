@admin @minor-trace-chemistry @read-only
Feature: Minor Trace Chemistry Admin View
  As a data manager
  I need to view legacy minor and trace chemistry data via the web admin interface
  So that I can browse historical chemistry analysis results without direct database access

  Background:
    Given I am authenticated as user "admin@nmbgmr.nmt.edu" with "Admin" role
    And the admin interface is available at "/admin"

  # ========== List View ==========

  @smoke @list-view
  Scenario: View minor trace chemistry list with default columns
    When I navigate to "/admin/n-m-a_-minor-trace-chemistry/list"
    Then I should see the minor trace chemistry list page
    And I should see the following columns:
      | Column Name              |
      | GlobalID                 |
      | Chemistry Sample Info ID |
      | Analyte                  |
      | Sample Value             |
      | Units                    |
      | Symbol                   |
      | Analysis Date            |
      | Analyses Agency          |
    And the list should be sorted by "Analysis Date" descending by default

  @list-view @search
  Scenario: Search minor trace chemistry by analyte
    Given minor trace chemistry records exist with analytes:
      | analyte     | sample_value | units |
      | Arsenic     | 0.005        | mg/L  |
      | Uranium     | 0.003        | mg/L  |
      | Selenium    | 0.001        | mg/L  |
    When I navigate to "/admin/n-m-a_-minor-trace-chemistry/list"
    And I enter "Arsenic" in the search box
    Then I should see results containing "Arsenic"
    But I should not see "Uranium" in the results

  @list-view @pagination
  Scenario: Paginate through minor trace chemistry list
    Given at least 100 minor trace chemistry records exist
    When I navigate to "/admin/n-m-a_-minor-trace-chemistry/list"
    Then I should see 50 records on page 1
    And I should see pagination controls

  # ========== Read-Only Restrictions ==========

  @read-only @security
  Scenario: Create action is disabled
    When I navigate to "/admin/n-m-a_-minor-trace-chemistry/list"
    Then I should not see a "Create" button
    And I should not see a "New" button

  @read-only @security
  Scenario: Direct access to create page is forbidden
    When I navigate to "/admin/n-m-a_-minor-trace-chemistry/create"
    Then I should see a 403 Forbidden response
    Or I should be redirected to the list page

  @read-only @security
  Scenario: Edit action is disabled
    Given a minor trace chemistry record exists
    When I navigate to the detail page for that record
    Then I should not see an "Edit" button
    And I should not see a "Save" button

  @read-only @security
  Scenario: Delete action is disabled
    Given a minor trace chemistry record exists
    When I navigate to the detail page for that record
    Then I should not see a "Delete" button

  # ========== Detail View ==========

  @detail-view @smoke
  Scenario: Detail page should load without error
    Given a minor trace chemistry record exists
    When I navigate to the detail page for that record
    Then the page should load successfully
    And I should not see an error message

  @detail-view
  Scenario: View minor trace chemistry record details
    Given a minor trace chemistry record exists with:
      | field                    | value                                |
      | analyte                  | Arsenic                              |
      | sample_value             | 0.005                                |
      | units                    | mg/L                                 |
      | symbol                   | As                                   |
      | analysis_method          | EPA 200.8                            |
      | analyses_agency          | NMED                                 |
    When I navigate to the detail page for that record
    Then I should see "Arsenic" as the analyte
    And I should see "0.005" as the sample value
    And I should see "mg/L" as the units
    And I should see "EPA 200.8" as the analysis method

  # ========== Navigation ==========

  @navigation
  Scenario: Minor Trace Chemistry appears in admin sidebar
    When I navigate to "/admin"
    Then I should see "Minor Trace Chemistry" in the sidebar
    And the icon should be "fa fa-flask"

  @navigation
  Scenario: Navigate to Minor Trace Chemistry from sidebar
    When I navigate to "/admin"
    And I click "Minor Trace Chemistry" in the sidebar
    Then I should be on "/admin/n-m-a_-minor-trace-chemistry/list"

# ============= EOF =============================================
