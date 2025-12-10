@backend
@BDMS-TBD
@production
Feature: Bulk upload well inventory from CSV
  As a hydrogeologist or data specialist
  I want to upload a CSV file containing well inventory data for multiple wells
  So that well records can be created efficiently and accurately in the system

  Background:
    Given a functioning api
    And valid lexicon values exist for:
      | lexicon category      |
      | contact_role          |
      | contact_type          |
      | phone_type            |
      | email_type            |
      | address_type          |
      | elevation_method      |
      | well_pump_type        |
      | well_purpose          |
      | well_hole_status      |
      | monitoring_frequency  |

  @positive @happy_path @BDMS-TBD
  Scenario: Uploading a valid well inventory CSV containing required and optional fields
    Given a valid CSV file for bulk well inventory upload
    And my CSV file is encoded in UTF-8 and uses commas as separators
    And my CSV file contains multiple rows of well inventory data
    And the CSV includes required fields:
      | required field name     |
      | project                 |
      | well_name_point_id      |
      | site_name               |
      | date_time               |
      | field_staff             |
      | utm_easting             |
      | utm_northing            |
      | utm_zone                |
      | elevation_ft            |
      | elevation_method        |
      | measuring_point_height_ft |
    And each "well_name_point_id" value is unique per row
    And "date_time" values are valid ISO 8601 timestamps with timezone offsets (e.g. "2025-02-15T10:30:00-08:00")
    And the CSV includes optional fields when available:
      | optional field name               |
      | field_staff_2                     |
      | field_staff_3                     |
      | contact_1_name                    |
      | contact_1_organization            |
      | contact_1_role                    |
      | contact_1_type                    |
      | contact_1_phone_1                 |
      | contact_1_phone_1_type            |
      | contact_1_phone_2                 |
      | contact_1_phone_2_type            |
      | contact_1_email_1                 |
      | contact_1_email_1_type            |
      | contact_1_email_2                 |
      | contact_1_email_2_type            |
      | contact_1_address_1_line_1        |
      | contact_1_address_1_line_2        |
      | contact_1_address_1_type          |
      | contact_1_address_1_state         |
      | contact_1_address_1_city          |
      | contact_1_address_1_postal_code   |
      | contact_1_address_2_line_1        |
      | contact_1_address_2_line_2        |
      | contact_1_address_2_type          |
      | contact_1_address_2_state         |
      | contact_1_address_2_city          |
      | contact_1_address_2_postal_code   |
      | contact_2_name                    |
      | contact_2_organization            |
      | contact_2_role                    |
      | contact_2_type                    |
      | contact_2_phone_1                 |
      | contact_2_phone_1_type            |
      | contact_2_phone_2                 |
      | contact_2_phone_2_type            |
      | contact_2_email_1                 |
      | contact_2_email_1_type            |
      | contact_2_email_2                 |
      | contact_2_email_2_type            |
      | contact_2_address_1_line_1        |
      | contact_2_address_1_line_2        |
      | contact_2_address_1_type          |
      | contact_2_address_1_state         |
      | contact_2_address_1_city          |
      | contact_2_address_1_postal_code   |
      | contact_2_address_2_line_1        |
      | contact_2_address_2_line_2        |
      | contact_2_address_2_type          |
      | contact_2_address_2_state         |
      | contact_2_address_2_city          |
      | contact_2_address_2_postal_code   |
      | directions_to_site                |
      | specific_location_of_well         |
      | repeat_measurement_permission     |
      | sampling_permission               |
      | datalogger_installation_permission |
      | public_availability_acknowledgement |
      | result_communication_preference   |
      | contact_special_requests_notes    |
      | ose_well_record_id                |
      | date_drilled                      |
      | completion_source                 |
      | total_well_depth_ft               |
      | historic_depth_to_water_ft        |
      | depth_source                      |
      | well_pump_type                    |
      | well_pump_depth_ft                |
      | is_open                           |
      | datalogger_possible               |
      | casing_diameter_ft                |
      | measuring_point_description       |
      | well_purpose                      |
      | well_purpose_2                    |
      | well_hole_status                  |
      | monitoring_frequency              |
      | sampling_scenario_notes           |
      | well_measuring_notes              |
      | sample_possible                   |
#    And all optional lexicon fields contain valid lexicon values when provided
#    And all optional numeric fields contain valid numeric values when provided
#    And all optional date fields contain valid ISO 8601 timestamps when provided

    When I upload the file to the bulk upload endpoint
    Then the system returns a 201 Created status code
    And the system should return a response in JSON format
#    And null values in the response are represented as JSON null
    And the response includes a summary containing:
      | summary_field              | value |
      | total_rows_processed       | 2 |
      | total_rows_imported        | 2 |
      | validation_errors_or_warnings | 0  |
    And the response includes an array of created well objects

  @positive @validation @column_order @BDMS-TBD
  Scenario: Upload succeeds when required columns are present but in a different order
    Given my CSV file contains all required headers but in a different column order
    And the CSV includes required fields:
      | required field name     |
      | project                 |
      | well_name_point_id      |
      | site_name               |
      | date_time               |
      | field_staff             |
      | utm_easting             |
      | utm_northing            |
      | utm_zone                |
      | elevation_ft            |
      | elevation_method        |
      | measuring_point_height_ft |
    When I upload the file to the bulk upload endpoint
    Then the system returns a 201 Created status code
    And the system should return a response in JSON format
    And all wells are imported

  @positive @validation @extra_columns @BDMS-TBD
  Scenario: Upload succeeds when CSV contains extra, unknown columns
    Given my CSV file contains extra columns but is otherwise valid
    When I upload the file to the bulk upload endpoint
    Then the system returns a 201 Created status code
    And the system should return a response in JSON format
    And all wells are imported

  @positive @validation @autogenerate_ids @BDMS-TBD
  Scenario: Upload succeeds and system auto-generates well_name_point_id when prefixed with "XY-
    Given my CSV file contains all valid columns but uses "XY-" prefix for well_name_point_id values
    When I upload the file to the bulk upload endpoint
    Then the system returns a 201 Created status code
    And the system should return a response in JSON format
    And all wells are imported with system-generated unique well_name_point_id values

  ###########################################################################
  # NEGATIVE VALIDATION SCENARIOS
  ###########################################################################
  @negative @validation @transactional_import @BDMS-TBD
  Scenario: No wells are imported when any row fails validation
    Given my CSV file contains 3 rows of data with 2 valid rows and 1 row missing the required "well_name_point_id"
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error for the row missing "well_name_point_id"
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has an invalid postal code format
    Given my CSV file contains a row  that has an invalid postal code format in contact_1_address_1_postal_code
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the invalid postal code format
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has a contact with a invalid phone number format
    Given my CSV file contains a row with a contact with a phone number that is not in the valid format
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the invalid phone number format
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has a contact with a invalid email format
    Given my CSV file contains a row with a contact with an email that is not in the valid format
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the invalid email format
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact without a contact_role
    Given my CSV file contains a row with a contact but is missing the required "contact_role" field for that contact
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the missing "contact_role" field
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact without a "contact_type"
    Given my CSV file contains a row with a contact but is missing the required "contact_type" field for that contact
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the missing "contact_type" value
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact with an invalid "contact_type"
    Given my CSV file contains a row with a contact_type value that is not in the valid lexicon for "contact_type"
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating an invalid "contact_type" value
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact with an email without an email_type
    Given my CSV file contains a row with a contact with an email but is missing the required "email_type" field for that email
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the missing "email_type" value
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact with a phone without a phone_type
    Given my CSV file contains a row with a contact with a phone but is missing the required "phone_type" field for that phone
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the missing "phone_type" value
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has contact with an address without an address_type
    Given my CSV file contains a row with a contact with an address but is missing the required "address_type" field for that address
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the missing "address_type" value
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when a row has utm_easting utm_northing and utm_zone values that are not within New Mexico
    Given my CSV file contains a row with utm_easting utm_northing and utm_zone values that are not within New Mexico
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating the invalid UTM coordinates
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when required fields are missing
    Given my CSV file contains rows missing a required field "well_name_point_id"
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes validation errors for all rows missing required fields
    And the response identifies the row and field for each error
    And no wells are imported

  @negative @validation @required_fields @BDMS-TBD
  Scenario Outline: Upload fails when a required field is missing
    Given my CSV file contains a row missing the required "<required_field>" field
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error for the "<required_field>" field
    And no wells are imported

    Examples:
      | required_field              |
      | project                     |
      | well_name_point_id          |
      | site_name                   |
      | date_time                   |
      | field_staff                 |
      | utm_easting                 |
      | utm_northing                |
      | utm_zone                    |
      | elevation_ft                |
      | elevation_method            |
      | measuring_point_height_ft   |

  @negative @validation @boolean_fields @BDMS-TBD
  Scenario: Upload fails due to invalid boolean field values
    Given my CSV file contains a row with an invalid boolean value "maybe" in the "is_open" field
#    And my CSV file contains other boolean fields such as "sample_possible" with valid boolean values
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating an invalid boolean value for the "is_open" field
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails when duplicate well_name_point_id values are present
    Given my CSV file contains one or more duplicate "well_name_point_id" values
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the response includes validation errors indicating duplicated values
    And each error identifies the row and field
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails due to invalid lexicon values
    Given my CSV file contains invalid lexicon values for "contact_role" or other lexicon fields
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the response includes validation errors identifying the invalid field and row
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails due to invalid date formats
    Given my CSV file contains invalid ISO 8601 date values in the "date_time" or "date_drilled" field
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the response includes validation errors identifying the invalid field and row
    And no wells are imported

  @negative @validation @BDMS-TBD
  Scenario: Upload fails due to invalid numeric fields
    Given my CSV file contains values that cannot be parsed as numeric in numeric-required fields such as "utm_easting"
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the response includes validation errors identifying the invalid field and row
    And no wells are imported


#  ###########################################################################
#  # FILE FORMAT SCENARIOS
#  ###########################################################################

  @negative @file_format @limits @BDMS-TBD
  Scenario: Upload fails when the CSV exceeds the maximum allowed number of rows
    Given my CSV file contains more rows than the configured maximum for bulk upload
    When I upload the file to the bulk upload endpoint
    Then the system returns a 400 status code
    And the system should return a response in JSON format
    And the response includes an error message indicating the row limit was exceeded
    And no wells are imported

  @negative @file_format @BDMS-TBD
  Scenario: Upload fails when file type is unsupported
    Given I have a non-CSV file
    When I upload the file to the bulk upload endpoint
    Then the system returns a 400 status code
    And the response includes an error message indicating unsupported file type
    And no wells are imported

  @negative @file_format @BDMS-TBD
  Scenario: Upload fails when the CSV file is empty
    Given my CSV file is empty
    When I upload the file to the bulk upload endpoint
    Then the system returns a 400 status code
    And the response includes an error message indicating an empty file
    And no wells are imported

  @negative @file_format @BDMS-TBD
  Scenario: Upload fails when CSV contains only headers
    Given my CSV file contains column headers but no data rows
    When I upload the file to the bulk upload endpoint
    Then the system returns a 400 status code
    And the response includes an error indicating that no data rows were found
    And no wells are imported

  ###########################################################################
  # HEADER & SCHEMA INTEGRITY SCENARIOS
  ###########################################################################

  @negative @validation @header_row @BDMS-TBD
  Scenario: Upload fails when a header row is repeated in the middle of the file
    Given my CSV file contains a valid but duplicate header row
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating a repeated header row
    And no wells are imported


  @negative @validation @header_row @BDMS-TBD
  Scenario: Upload fails when the header row contains duplicate column names
    Given my CSV file header row contains the "contact_1_email_1" column name more than once
    When I upload the file to the bulk upload endpoint
    Then the system returns a 422 Unprocessable Entity status code
    And the system should return a response in JSON format
    And the response includes a validation error indicating duplicate header names
    And no wells are imported


  ###########################################################################
  # DELIMITER & QUOTING / EXCEL-RELATED SCENARIOS
  ###########################################################################

  @negative @file_format @delimiter @BDMS-TBD
  Scenario Outline: Upload fails when CSV uses an unsupported delimiter
    Given my file is named with a .csv extension
    And my file uses "<delimiter_description>" as the field delimiter instead of commas
    When I upload the file to the bulk upload endpoint
    Then the system returns a 400 status code
    And the system should return a response in JSON format
    And the response includes an error message indicating an unsupported delimiter
    And no wells are imported

    Examples:
      | delimiter_description |
      | semicolons            |
      | tab characters        |

  @positive @file_format @quoting @BDMS-TBD
  Scenario: Upload succeeds when fields contain commas inside properly quoted values
    Given my CSV file header row contains all required columns
    And my CSV file contains a data row where the "site_name" field value includes a comma and is enclosed in quotes
#    And all other required fields are populated with valid values
    When I upload the file to the bulk upload endpoint
    Then the system returns a 201 Created status code
    And the system should return a response in JSON format
    And all wells are imported
#
#  @negative @validation @numeric @excel @BDMS-TBD
#  Scenario: Upload fails when numeric fields are provided in Excel scientific notation format
#    Given my CSV file contains a numeric-required field such as "utm_easting"
#    And Excel has exported the "utm_easting" value in scientific notation (for example "1.2345E+06")
#    When I upload the file to the bulk upload endpoint
#    Then the system returns a 422 Unprocessable Entity status code
#    And the system should return a response in JSON format
#    And the response includes a validation error indicating an invalid numeric format for "utm_easting"
#    And no wells are imported