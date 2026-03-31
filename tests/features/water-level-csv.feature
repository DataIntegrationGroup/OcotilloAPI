@cli
@backend
@BDMS-TBD
Feature: Bulk upload water level entries from CSV via CLI
  As a hydrogeologist or data specialist
  I want to upload a CSV file containing water level entry data for multiple wells using a CLI command
  So that groundwater-level records can be created efficiently and accurately in the system

  @positive @happy_path @BDMS-TBD @cleanup_samples
  Scenario: Uploading a valid water level entry CSV containing required and optional fields
    Given a valid CSV file for bulk water level entry upload
    And my CSV file is encoded in UTF-8 and uses commas as separators
    And my CSV file contains multiple rows of water level entry data
    And the water level CSV includes required fields:
      | required field name   |
      | field_staff           |
      | well_name_point_id    |
      | field_event_date_time |
      | water_level_date_time |
      | measuring_person      |
      | sample_method         |
    And each "well_name_point_id" value matches an existing well
    And "field_event_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T08:00:00")
    And "water_level_date_time" values are valid ISO 8601 timezone-naive datetime strings (e.g. "2025-02-15T10:30:00")
    And when provided, "sample_method", "level_status", and "data_quality" values are valid lexicon values
    And the water level CSV includes optional fields when available:
      | optional field name |
      | field_staff_2       |
      | field_staff_3       |
      | mp_height           |
      | level_status        |
      | depth_to_water_ft   |
      | data_quality        |
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

  @positive @validation @aliases @BDMS-TBD @cleanup_samples
  Scenario: Upload succeeds when legacy alias headers are used
    Given my water level CSV file uses legacy alias headers for measurement date, sampler, and measuring point height
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with code 0
    And stdout should be valid JSON
    And all water level entries are imported
    And stderr should be empty

  @positive @validation @extra_columns @BDMS-TBD @cleanup_samples
  Scenario: Upload succeeds when CSV contains extra columns
    Given my water level CSV file contains extra columns but is otherwise valid
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with code 0
    And stdout should be valid JSON
    And all water level entries are imported
    And stderr should be empty

  @positive @validation @partial_success @BDMS-TBD @cleanup_samples
  Scenario: Valid rows are imported when another row fails validation
    Given my water level CSV contains 3 rows with 2 valid rows and 1 row missing the required "well_name_point_id"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with code 0
    And stdout should be valid JSON
    And stdout includes a summary containing:
      | summary_field                 | value |
      | total_rows_processed          | 3     |
      | total_rows_imported           | 2     |
      | validation_errors_or_warnings | 1     |
    And stderr should contain a validation error for the row missing "well_name_point_id"

  @negative @validation @required_fields @BDMS-TBD
  Scenario Outline: Upload fails when a required field is missing
    Given my water level CSV file contains a row missing the required "<required_field>" field
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with a non-zero exit code
    And stderr should contain a validation error for the "<required_field>" field
    And no water level entries are imported

    Examples:
      | required_field        |
      | field_staff           |
      | well_name_point_id    |
      | field_event_date_time |
      | water_level_date_time |
      | measuring_person      |
      | sample_method         |

  @negative @validation @date_formats @BDMS-TBD
  Scenario: Upload fails due to invalid date formats
    Given my CSV file contains invalid ISO 8601 date values in the "water_level_date_time" field
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported

  @negative @validation @numeric_fields @BDMS-TBD
  Scenario: Upload fails due to invalid numeric fields
    Given my CSV file contains values that cannot be parsed as numeric in numeric fields such as "mp_height" or "depth_to_water_ft"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported

  @negative @validation @lexicon_values @BDMS-TBD
  Scenario: Upload fails due to invalid lexicon values for water level descriptor fields
    Given my CSV file contains invalid lexicon values for "sample_method", "level_status", or "data_quality"
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported

  @negative @validation @measuring_person @BDMS-TBD
  Scenario: Upload fails when measuring_person does not match supplied field staff
    Given my water level CSV file contains a row where measuring_person is not one of the supplied field staff
    When I run the CLI command:
      """
      oco water-levels bulk-upload --file ./water_levels.csv --output json
      """
    Then the command exits with a non-zero exit code
    And stderr should contain validation errors identifying the invalid field and row
    And no water level entries are imported
