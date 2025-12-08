@backend @BDMS-227
Feature: Retrieve additional well information by well ID
  As a hydrogeologist or data specialist
  I want to view additional well attributes with specific physical and operational characteristics
  So that I have all necessary well data to confidently complete fieldwork

  Background:
    Given a functioning api
    And the system has valid well and location data in the database

  Scenario: Retrieve additional well information for an existing well
    When the user retrieves the well by ID via path parameter
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And null values in the response should be represented as JSON null (not placeholder strings)

    # Permissions / Operational OK flags
    And the response should include whether repeat measurement permission is granted for the well
    And the response should include whether sampling permission is granted for the well
    And the response should include whether datalogger installation permission is granted for the well

    # Well Construction Information
    And the response should include the completion date of the well
    And the response should include the source of the completion information
    And the response should include the driller name
    And the response should include the construction method
    And the response should include the source of the construction information

    # Additional Well Physical Properties
    And the response should include the casing diameter in inches
    And the response should include the casing depth in feet below ground surface
    And the response should include the casing materials
    And the response should include the well pump type (previously well_type field)
    And the response should include the well pump depth in feet (new field)
    And the response should include whether the well is open and suitable for a datalogger

    # Aquifer / Geology Information
    And the response should include the formation as the formation zone of well completion
    And the response should include the aquifer class code to classify the aquifer into aquifer system.
    And the response should include the aquifer type as the type of aquifers penetrated by the well
