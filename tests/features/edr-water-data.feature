@backend @edr
Feature: OGC API - EDR delivery of water-level and water-chemistry data
  As a consumer of Bureau observational data
  I want to query groundwater levels and water chemistry through the standard
  OGC API - EDR query patterns on the existing /ogcapi (pygeoapi) mount
  So that I can retrieve point, area, location and time-filtered observations
  as CoverageJSON without a bespoke per-dataset client.

  # Executable spec for ADR3 (see ADR3.md). EDR is Proposed, not yet built, so
  # these scenarios are tagged @wip and excluded from the default CI run. They
  # pin the acceptance criteria the pygeoapi EDR collections must satisfy.
  #
  # Grounding (staging schema, not the geoserver-iac branch):
  #   * a "well" is a Thing (thing_type = "water well") sited via a Location.point
  #   * manual water levels        -> Observation (parameter "groundwater level")
  #   * transducer water levels    -> TransducerObservation, grouped by
  #                                   TransducerObservationBlock, per Deployment
  #   * water chemistry            -> Observation tied to a Sample + Parameter
  #   * a transducer "instance"    -> a Deployment (install/removal, interval) + Sensor
  #   * publication gate           -> release_status = 'public' (ogc_* views)
  # Two EDR collections are added to the existing pygeoapi mount: "waterlevels"
  # and "water_chemistry", backed by ogc_waterlevels / ogc_water_chemistry views.

  Background:
    Given a functioning api
    And the EDR collections are configured on the /ogcapi mount

  Scenario: The collections catalog advertises the two EDR collections
    When a client requests /ogcapi/collections
    Then the system should return a 200 status code
    And the collections catalog includes the EDR collection "waterlevels"
    And the collections catalog includes the EDR collection "water_chemistry"

  Scenario: The waterlevels collection declares EDR metadata
    When a client requests the EDR collection metadata for "waterlevels"
    Then the system should return a 200 status code
    And the collection declares a spatial extent
    And the collection declares a temporal extent
    And the collection declares the parameter name "groundwater level"
    And the collection declares the EDR query patterns "position,area,locations"

  Scenario: Depth-to-water at a well over a bounded time range as CoverageJSON
    Given a well with water-level observations
    When the client requests the "waterlevels" location series for that well over "2020-01-01T00:00:00Z/2024-01-01T00:00:00Z"
    Then the system should return a 200 status code
    And the response is CoverageJSON
    And the coverage exposes the parameter "groundwater level"
    And every observation datetime is within "2020-01-01T00:00:00Z/2024-01-01T00:00:00Z"

  Scenario: A well series merges manual and transducer readings on one axis
    Given a well with both manual and transducer water-level data
    When the client requests the "waterlevels" location series for that well over the full period
    Then the system should return a 200 status code
    And the coverage contains both manual and transducer readings

  Scenario: Transducer deployments are exposed as EDR instances
    Given a well with a transducer deployment
    When the client requests the "waterlevels" instances for that well
    Then the system should return a 200 status code
    And at least one EDR instance is listed
    And each EDR instance has an identifier

  Scenario: Water chemistry within a polygon filtered by analyte
    Given a polygon that covers wells with chemistry data
    When the client requests "water_chemistry" for that area with parameter name "pH"
    Then the system should return a 200 status code
    And the response is CoverageJSON
    And every returned value is for the parameter "pH"

  Scenario: Only public records are published through EDR
    Given a well that has non-public water-level and chemistry records
    When the client requests the "waterlevels" location series for that well over the full period
    Then the system should return a 200 status code
    And no returned record has a release_status other than "public"
    When the client requests the "water_chemistry" location series for that well over the full period
    Then the system should return a 200 status code
    And no returned record has a release_status other than "public"

  Scenario: Conformance declares EDR support
    When a client requests /ogcapi/conformance
    Then the system should return a 200 status code
    And the conformance classes include an OGC API - EDR core class
