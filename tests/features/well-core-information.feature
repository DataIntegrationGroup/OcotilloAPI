@backend @BDMS-221
Feature: Retrieve core well information by well ID
  As a hydrogeologist or data specialist
  I want to view clearly labeled core physical attributes and identifiers for the well in a well information page section
  so that I can assess key well characteristics at a glance

  Background:
    Given a functioning api
    And the system has valid well and location data in the database

  Scenario: Retrieve core well information for an existing well
    When the user retrieves the well by ID via path parameter
    Then the system should return a 200 status code
    And the system should return a response in JSON format
    And null values in the response should be represented as JSON null (not placeholder strings)

    # Well names and projects
    And the response should include the well name (point ID) (i.e. NM-1234)
    And the response should include the project(s) or group(s) associated with the well

    # Well Purpose and Status and Monitoring Status
    And the response should include the purpose of the well (current use)
    And the response should include the well hole status of the well as the status of the hole in the ground (from previous Status field)
    And the response should include the monitoring frequency (new field)
    And the response should include whether the well is currently being monitored with status text if applicable (from previous MonitoringStatus field)

    # Data Lifecycle and Public Visibility
    # NEEDS USER RESEARCH - keep both under release_status for now? (previously PublicRelease)
    And the response should include the release status of the well record

    # Well Physical Properties
    And the response should include the hole depth in feet
    And the response should include the well depth in feet
    And the response should include the source of the well depth information

    # Measuring Point Information
    And the response should include the description of the measuring point
    And the response should include the measuring point height in feet

    # Location Information
    # GeoJSON spec format RFC 7946 (Aug 2016) requires coordinates to be decimal degrees in WGS84
    And the response should include location information in GeoJSON spec format RFC 7946
    And the response should include a geometry object with type "Point" and coordinates array [longitude, latitude, elevation]
    And the response should include the elevation in feet with vertical datum NAVD88 in the properties
    And the response should include the elevation method (i.e. interpolated from digital elevation model) in the properties
    And the response should include the UTM coordinates with datum NAD83 in the properties

    # Alternate Identifiers
    And the response should include any alternate IDs for the well like the NMBGMR site_name (i.e. John Smith Well), USGS site number, or the OSE well ID and OSE well tag ID

