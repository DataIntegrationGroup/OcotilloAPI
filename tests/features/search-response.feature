@backend @BDMS-169
Feature: Unified search API returns grouped results
  As a user
  I want to search for contacts, wells, and springs
  So that I can quickly find relevant information across multiple data types

  Background:
    Given a functioning api
    And the system has valid contact, well, and spring records in the database

  @positive @happy_path
  Scenario: Retrieve mixed search results
    When the user searches for "<search_term>"
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And the response should include results grouped by:
      | Contacts | Wells | Springs |
    And each result should include a label, group, and properties

  @positive @happy_path
  Scenario: Retrieve contact results
    When the user searches for "<contact_search_term>"
    Then the system should return a 200 status code
    And the response should include a "Contacts" group
    And each contact result should include:
      #| TODO: use correct field name syntax |
      | id | first_name | last_name | email | phone | address | associated_things |

  @positive @happy_path
  Scenario: Retrieve well results
    When the user searches for "<well_search_term>"
    Then the system should return a 200 status code
    And the response should include a "Wells" group
    And each well result should include:
      #| TODO: use correct field name syntax |
      | thing_type | id | name | alternate site name | contact first name | contact last name | contact id | county |

  @positive @happy_path
  Scenario: Retrieve spring results
    When the user searches for "<spring_search_term>"
    Then the system should return a 200 status code
    And the response should include a "Springs" group
    And each spring result should include:
      | thing_type | id |