# features/cli/bulk_upload_water_levels.feature

@skip
@cli
@backend
@BDMS-TBD
@production
Feature: Bulk upload water level entries from CSV via CLI
  As a hydrogeologist or data specialist
  I want to upload a CSV file containing water level entry data for multiple wells using a CLI command
  So that water level records can be created efficiently and accurately in the system

#  Background:
#    Given the CLI binary "bdms" is installed and available on the PATH
#    And I have a valid CLI configuration for the target environment
#    And valid lexicon values exist for:
#      | lexicon category |
#      | sample_method    |
#      | level_status     |
#      | data_quality     |

  @positive @happy_path @BDMS-TBD
  Scenario: Uploading a valid water level entry CSV containing required and optional fields
    Given a valid CSV file for bulk water level entry upload
    And my CSV file is encoded in UTF-8 and uses commas as separators
    And my CSV file contains multiple rows of water level entry data
    And the CSV includes required fields:
      | required field name   |
      | field_staff           |
      | well_name_point_id    |
      | field_event_date_time |
      | water_level_date_time |
      | measuring_person      |
      | sample_method         |
      | mp_height             |
      | level_status          |
      | depth_to_water_ft     |
      | data_quality          |
    And each "well_name_point_id" value matches an existing well
    And "measurement_date_time" values are valid ISO 8601 timestamps with timezone offsets (e.g. "2025-02-15T10:30:00-08:00")
    And the CSV includes optional fields when available:
      | optional field name |
      | field_staff_2       |
      | field_staff_3       |
      | water_level_notes   |
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with code 0
    And stdout should be valid JSON
    And stdout includes a summary containing:
      | summary_field                 | value |
      | total_rows_processed          | 2     |
      | total_rows_imported           | 2     |
      | validation_errors_or_warnings | 0     |
    And stdout includes an array of created water level entry objects
    And stderr should be empty

  @positive @validation @column_order @BDMS-TBD
  Scenario: Upload succeeds when required columns are present but in a different order
    Given my CSV file contains all required headers but in a different column order
    And the CSV includes required fields:
      | required field name   |
      | well_name_point_id    |
      | water_level_date_time |
      | measuring_person      |
      | sample_method         |
      | mp_height             |
      | level_status          |
      | depth_to_water_ft     |
      | data_quality          |
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with code 0
    And all water level entries are imported
    And stderr should be empty

  @positive @validation @extra_columns @BDMS-TBD
  Scenario: Upload succeeds when CSV contains extra, unknown columns
    Given my CSV file contains extra columns but is otherwise valid
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with code 0
    And all water level entries are imported
    And stderr should be empty

  ###########################################################################
  # NEGATIVE VALIDATION SCENARIOS
  ###########################################################################

  @negative @validation @BDMS-TBD
  Scenario: No water level entries are imported when any row fails validation
    Given my CSV file contains 3 rows of data with 2 valid rows and 1 row missing the required "well_name_point_id"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with a non-zero exit code
    And stderr should contain a validation error for the row missing "well_name_point_id"
    And no water level entries are imported

  @negative @validation @required_fields @BDMS-TBD
  Scenario Outline: Upload fails when a required field is missing
    Given my CSV file contains a row missing the required "<required_field>" field
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with a non-zero exit code
    And stderr should contain a validation error for the "<required_field>" field
    And no water level entries are imported

    Examples:
      | required_field        |
      | well_name_point_id    |
      | water_level_date_time |
      | measuring_person      |
      | sample_method         |
      | mp_height             |
      | level_status          |
      | depth_to_water_ft     |
      | data_quality          |

  @negative @validation @date_formats @BDMS-TBD
  Scenario: Upload fails due to invalid date formats
    Given my CSV file contains invalid ISO 8601 date values in the "water_level_date_time" field
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported

  @negative @validation @numeric_fields @BDMS-TBD
  Scenario: Upload fails due to invalid numeric fields
    Given my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "mp_height" or "depth_to_water_ft"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported

  @negative @validation @lexicon_values @BDMS-TBD
  Scenario: Upload fails due to invalid lexicon values
    Given my CSV file contains invalid lexicon values for "measuring_person", "sample_method", "level_status", or "data_quality"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported
