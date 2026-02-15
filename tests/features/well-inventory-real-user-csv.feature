@backend
@cli
Feature: Well inventory CLI with real user-entered CSV data
  As a CLI user
  I want to run the well inventory import against real user-entered data
  So that parsing and summary behavior is validated against production-like input

  Background:
    Given a functioning cli
    And valid lexicon values exist for:
      | lexicon category      |
      | role                  |
      | contact_type          |
      | phone_type            |
      | email_type            |
      | address_type          |
      | elevation_method      |
      | well_pump_type        |
      | well_purpose          |
      | status_value          |
      | monitoring_frequency  |
      | sample_method         |
      | level_status          |
      | data_quality          |

  @validation
  Scenario: Run CLI import on the real user-entered well inventory CSV file with validation-heavy input
    Given I use the real user-entered well inventory CSV file
    And my CSV file is encoded in UTF-8 and uses commas as separators
    And my CSV file contains multiple rows of well inventory data
    When I run the well inventory bulk upload command
    Then the command exits with a non-zero exit code
    And the system should return a response in JSON format
    And the response includes one or more validation errors
    And each validation error contains row field and error details
    And the response summary reports all rows were processed from the source CSV
    And the response summary includes import and validation counts
    And no wells are imported when validation errors are present
    And the command exit code matches whether validation errors were reported
