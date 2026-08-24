Feature: OGC Feature Layer Cleanup — Sprint 1
  As an OGC API consumer
  I want the Ocotillo API feature layers to be accurately filtered, correctly named, and reliably configured
  So that I can depend on the API for scientific and operational use

  # Sprint 1 scope: A1, A2, A3, A4, A6, A11, A13, A16, A17, A18, A22, A23
  #
  # Deferred to Sprint 2:
  #   A5  — int(None) runtime warning in pygeoapi/api/itemtypes.py
  #   A7  — Level 1 display title pass (non-breaking naming update)
  #   A8  — Layer ID renames (Level 2 vs Level 3 decision pending)
  #   A9  — Publication predicate policy per layer family (domain-owner sign-off required)
  #   A10 — Per-layer SQL publication filters (depends on A9)
  #   A12 — Sentinel date nulling in chemistry layers
  #   A14 — Group A view template split to remove non-well schema bleed
  #   A15 — Materialized view refresh schedule documentation
  #   A19 — Sparse Group A layer hiding
  #   A20 — Extended test coverage for all 22 configured collections
  #   A21 — Separate database roles for public and internal OGC access

  Background:
    Given the Ocotillo API is running

  # ---------------------------------------------------------------------------
  # A1 — Apply release_status = 'public' filter to all OGC views
  # ---------------------------------------------------------------------------

  @backend @ogc-exposure @sprint-1 @high-priority @A1 @production @migration-mutates-schema @cleanup_samples
  Scenario: Sprint 1 migration restricts all ogc_* views to public records
    Given a clean database state before the Sprint 1 migration
    When the Sprint 1 Alembic migration is applied
    Then each ogc_* view returns only records with release_status "public"

  @backend @ogc-exposure @sprint-1 @high-priority @A1 @production @migration-mutates-schema @cleanup_samples
  Scenario: Sprint 1 migration can be reversed without error
    Given the Sprint 1 migration has been applied
    When the Sprint 1 migration downgrade is run
    Then each ogc_* view returns the same count of public records as before the migration
    And each ogc_* view returns the same count of private records as before the migration
    And each ogc_* view returns the same count of draft records as before the migration
    And no database errors are raised

  @backend @ogc-exposure @sprint-1 @high-priority @A1 @production @cleanup_samples
  Scenario: Non-public records are excluded from every exposure-affected OGC layer
    Given the Sprint 1 migration has been applied
    When a public client requests items from each of the following layers:
      | layer-id                      |
      | water_wells                   |
      | springs                       |
      | perennial_streams             |
      | meteorological_stations       |
      | diversions_surface_water      |
      | lakes_ponds_reservoirs        |
      | water_well_summary            |
      | depth_to_water_trend_wells    |
      | water_elevation_wells         |
      | major_chemistry_results       |
      | minor_chemistry_wells         |
      | latest_tds_wells              |
      | actively_monitored_wells      |
      | project_areas                 |
    Then each response contains only records where release_status is "public"
    And no response contains a record where release_status is "private"
    And no response contains a record where release_status is "draft"
    # other_things, avg_tds_wells, latest_depth_to_water_wells and locations
    # are not listed above: A16/A17/A18 took them off the public catalog, so a
    # public client can no longer request their items. A1's filter still
    # applies to their views, which the SQL-level scenarios above cover.

  @backend @ogc-exposure @sprint-1 @high-priority @A1 @production
  Scenario: project_areas returns 56 rows after all records are updated to public
    Given all 56 project_areas records have been updated from release_status "draft" to release_status "public"
    When a client requests features from the project_areas layer
    Then the response contains 56 features
    And the response HTTP status is 200
    And all returned features have release_status "public"
    # The "Given" precondition above is satisfied by a dedicated data
    # migration (not the schema migration that adds the release_status
    # filter) -- see the project_areas data migration in this ticket's
    # implementation. Automated tests verify the underlying property
    # (every project_area-bearing group ends up public), not the literal
    # count 56, which is specific to today's real production data and is
    # spot-checked manually against the target environment instead.

  @backend @ogc-exposure @sprint-1 @high-priority @A1 @production @migration-mutates-schema @cleanup_samples
  Scenario: The 4 already-consistent layers are unaffected by the migration
    Given the following layers were already filtering correctly before the migration:
      | layer-id                        |
      | ephemeral_streams               |
      | rock_sample_locations           |
      | soil_gas_sample_locations       |
      | outfalls_wastewater_return_flow |
    When the Sprint 1 migration is applied
    Then each of those layers returns the same feature count as before the migration

  # ---------------------------------------------------------------------------
  # A2 — Replace OGC server metadata placeholders in pygeoapi-config.yml
  # ---------------------------------------------------------------------------

  @backend @ogc-infrastructure @sprint-1 @high-priority @A2 @production
  Scenario: Service metadata contains no placeholder or example.com values
    Given the service configuration has been updated with accurate metadata
    When a client requests the /ogcapi landing page as JSON, as HTML, and as OpenAPI
    Then no response body contains an "example.com" string

  @backend @ogc-infrastructure @sprint-1 @high-priority @A2 @production
  Scenario: Service metadata reflects correct contact and provider information
    When a client requests the /ogcapi OpenAPI document
    Then the service metadata fields match the following values:
      | field         | expected-value            |
      | provider_url  | https://geoinfo.nmt.edu   |
      | contact_name  | Ocotillo Support, NMBGMR  |
      | contact_email | ocotillo-nmbg@nmt.edu     |
    And the terms of service URL resolves to the service disclaimer page
    # The three fields above are asserted against the OpenAPI document, not
    # the JSON landing page: in pygeoapi 0.23.5 the JSON landing page carries
    # only title, description, and links. terms_of_service is checked by
    # resolving it, because an advertised URL that 404s is no better than a
    # placeholder.

  # ---------------------------------------------------------------------------
  # A3 — Fix broken README example URLs
  # ---------------------------------------------------------------------------

  @backend @ogc-infrastructure @sprint-1 @high-priority @A3
  Scenario Outline: README example URLs return valid GeoJSON
    Given the README example URLs reference the water_wells collection
    When a client requests "<url-path>"
    Then the response HTTP status is 200
    And the response Content-Type is "application/geo+json"

    Examples:
      | url-path                                                              |
      | /ogcapi/collections/water_wells/items?limit=5                         |
      | /ogcapi/collections/water_wells/items?datetime=2020-01-01/2024-01-01  |

  # ---------------------------------------------------------------------------
  # A4/A6 — actively_monitored_wells covers all groups; name unchanged
  # ---------------------------------------------------------------------------
  # A6's original rename to water_level_network_wells was withdrawn: the name
  # was fine, the filter was too narrow. A4 (brittle group-name filter) and A6
  # (naming) are resolved together by the same SQL change.

  @backend @ogc-data-currency @sprint-1 @high-priority @A4
  Scenario: Layer includes a well from a group other than Water Level Network
    Given a well is currently monitored under the "Test Other Group" group
    When a client requests features from the actively_monitored_wells layer
    Then the response includes that well

  @backend @ogc-data-currency @sprint-1 @high-priority @A4
  Scenario: Layer is resilient to group display name changes
    Given the "Water Level Network" group display name is changed to "Water Level Monitoring Network"
    When a client requests features from the actively_monitored_wells layer
    Then wells in that group still appear in the response

  @backend @ogc-naming @sprint-1 @high-priority @A6
  Scenario: Layer keeps its existing ID and is discoverable in the collections catalog
    When a client requests /ogcapi/collections
    Then the actively_monitored_wells collection appears in the response
    And the water_level_network_wells collection does not appear in the response

  # ---------------------------------------------------------------------------
  # A11 — Stand up authenticated internal OGC mount at /ogcapi-internal
  # ---------------------------------------------------------------------------

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Anonymous request to internal OGC endpoint is rejected
    When an unauthenticated client requests /ogcapi-internal/collections
    Then the response HTTP status is 401

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Request with insufficient role to internal OGC endpoint is rejected
    Given the client presents a valid token with role "public-viewer"
    When the client requests /ogcapi-internal/collections
    Then the response HTTP status is 403

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Authenticated internal staff can access /ogcapi-internal collections
    Given an internal staff member with the required role is authenticated via Authentik
    When the staff member requests /ogcapi-internal/collections
    Then the response HTTP status is 200
    And the response includes collections not available on the public /ogcapi endpoint

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Internal collections expose private and draft records
    Given an authenticated internal staff member
    When the staff member requests items from the "water_wells" internal collection
    Then records with a release_status other than "public" are included in the response

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Internal database relations are separate from public relations
    Given the /ogcapi-internal mount has been deployed
    When the database schema is inspected
    Then the database schema contains relations prefixed with "ogc_internal_"
    And no ogc_internal_ relation is shared with the public /ogcapi endpoint

  @backend @ogc-infrastructure @sprint-1 @high-priority @A11 @production
  Scenario: Public /ogcapi surface is unaffected by the internal mount
    When a client requests /ogcapi/collections
    Then no collection in the response has an id prefixed "ogc_internal_"

  # ---------------------------------------------------------------------------
  # A13 — Add last_observation_date column to Group A view template
  # ---------------------------------------------------------------------------

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13
  Scenario: last_observation_date column is present in all Group A layers
    When a client requests items from each of the following layers:
      | layer-id                          |
      | water_wells                       |
      | springs                           |
      | perennial_streams                 |
      | meteorological_stations           |
      | ephemeral_streams                 |
      | rock_sample_locations             |
      | diversions_surface_water          |
      | lakes_ponds_reservoirs            |
      | soil_gas_sample_locations         |
      | outfalls_wastewater_return_flow   |
    Then each feature includes a last_observation_date property
    # other_things is not listed: it is in the Group A view template, but A18
    # took it off the public catalog — it is only reachable on /ogcapi-internal.

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13
  Scenario: last_observation_date is NULL for things with no associated observations
    Given monitoring locations with no linked observations exist in each of the following layers:
      | layer-id                          |
      | water_wells                       |
      | springs                           |
      | perennial_streams                 |
      | meteorological_stations           |
      | ephemeral_streams                 |
      | rock_sample_locations             |
      | diversions_surface_water          |
      | lakes_ponds_reservoirs            |
      | soil_gas_sample_locations         |
      | outfalls_wastewater_return_flow   |
    When a client requests those features
    Then each feature's last_observation_date property is null
    # other_things is not listed: it is in the Group A view template, but A18
    # took it off the public catalog — it is only reachable on /ogcapi-internal.

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13
  Scenario: Consumers can filter Group A layers by last_observation_date
    Given each of the following Group A layers has features with last_observation_date values "2019-06-01" and "2023-06-01":
      | layer-id                        |
      | water_wells                     |
      | springs                         |
      | perennial_streams               |
      | meteorological_stations         |
      | ephemeral_streams               |
      | rock_sample_locations           |
      | diversions_surface_water        |
      | lakes_ponds_reservoirs          |
      | soil_gas_sample_locations       |
      | outfalls_wastewater_return_flow |
    When a client requests items from each of those layers with filter
      """
      last_observation_date > '2021-01-01'
      """
    Then only features with a last_observation_date of "2023-06-01" are returned from each layer
    # other_things is not listed: it is in the Group A view template, but A18
    # took it off the public catalog — it is only reachable on /ogcapi-internal.

  # ---------------------------------------------------------------------------
  # A16 — Hide avg_tds_wells and latest_depth_to_water_wells from public catalog
  # ---------------------------------------------------------------------------

  @backend @ogc-data-currency @sprint-1 @medium-priority @A16 @production
  Scenario: avg_tds_wells is absent from the public collections catalog
    When a client requests /ogcapi/collections
    Then the response does not include a collection with id avg_tds_wells

  @backend @ogc-data-currency @sprint-1 @medium-priority @A16 @production
  Scenario: latest_depth_to_water_wells is absent from the public collections catalog
    When a client requests /ogcapi/collections
    Then the response does not include a collection with id latest_depth_to_water_wells

  @backend @ogc-data-currency @sprint-1 @medium-priority @A16 @production
  Scenario: Backing matviews for hidden layers are retained in the database
    Given avg_tds_wells and latest_depth_to_water_wells have been removed from the service catalog
    When the database schema is inspected
    Then the materialized view for avg_tds_wells exists in the database schema
    And the materialized view for latest_depth_to_water_wells exists in the database schema

  # ---------------------------------------------------------------------------
  # A17 — Hide locations layer from the public catalog
  # ---------------------------------------------------------------------------

  @backend @ogc-data-currency @sprint-1 @medium-priority @A17 @production
  Scenario: locations is absent from the public collections catalog
    When a client requests /ogcapi/collections
    Then the response does not include a collection with id locations

  @backend @ogc-data-currency @sprint-1 @medium-priority @A17 @production
  Scenario: Underlying locations table is retained in the database after catalog removal
    Given the locations entry has been removed from the service configuration
    When the database schema is inspected
    Then the locations table still exists

  # ---------------------------------------------------------------------------
  # A18 — Remove other_things from the public catalog
  # ---------------------------------------------------------------------------

  @backend @ogc-naming @sprint-1 @medium-priority @A18 @production
  Scenario: other_things is absent from the public collections catalog
    When a client requests /ogcapi/collections
    Then the response does not include a collection with id other_things

  # The A18 review found internal usage: /ogcapi-internal still publishes the
  # layer to staff GIS clients off ogc_internal_other_things, and the public
  # ogc_other_things view is still built by the shared Group A view template.
  # Both views are therefore retained.
  @backend @ogc-naming @sprint-1 @medium-priority @A18 @production
  Scenario: other_things backing views are retained because the internal mount uses them
    Given the other_things view has at least one reference in the application codebase
    When the database schema is inspected
    Then the other_things backing view still exists in the database schema
    And the internal other_things backing view still exists in the database schema

  # ---------------------------------------------------------------------------
  # A22 — Verify NULL measuring_point_height assumption for water level layers
  # ---------------------------------------------------------------------------

  # A22 policy gate: an ADR must be written confirming whether NULL
  # measuring_point_height is treated as zero or excluded from calculations.
  # Tracked in ticket — not enforced as a Behave scenario.

  @backend @ogc-data-currency @sprint-1 @medium-priority @A22
  Scenario: Layer descriptions are updated when the NULL-as-zero assumption is confirmed
    Given the NULL measuring_point_height handling policy is documented as "treat as zero (ground surface level)"
    When the layer descriptions are updated
    Then each of the following layer descriptions documents the zero assumption:
      | layer-id                      |
      | water_well_summary            |
      | depth_to_water_trend_wells    |
      | water_elevation_wells         |
    And each of those layers is reclassified to production-ready status

  @backend @ogc-data-currency @sprint-1 @medium-priority @A22
  Scenario: Null handling logic is corrected and matviews rebuilt when assumption is not confirmed
    Given the NULL measuring_point_height handling policy is documented as "flag as unverified and exclude from depth calculations"
    When the corrected view definitions are applied
    Then the null handling logic for measuring_point_height is corrected in each of the following views:
      | layer-id                      |
      | water_well_summary            |
      | depth_to_water_trend_wells    |
      | water_elevation_wells         |
    And all affected materialized views are rebuilt and refreshed
    And the depth-to-water value for a well with NULL measuring_point_height is null or absent

  # ---------------------------------------------------------------------------
  # A23 — Bump advertised spatial extent to include northern border features
  # ---------------------------------------------------------------------------

  @backend @ogc-geometry @sprint-1 @low-priority @A23
  Scenario: Spatial extent northern latitude boundary is updated in config
    Given the service configuration has been updated with the corrected spatial extent
    When the service configuration is loaded
    Then the advertised northern latitude boundary is "37.10"

  @backend @ogc-geometry @sprint-1 @low-priority @A23
  Scenario: Landing page reflects the updated spatial extent
    When a client requests the /ogcapi landing page
    Then the spatial extent northern boundary in the response is "37.10"

  @backend @ogc-geometry @sprint-1 @low-priority @A23
  Scenario: Collections response reflects the updated spatial extent
    When a client requests /ogcapi/collections
    Then the spatial extent northern boundary in the response is "37.10"

  @backend @ogc-geometry @sprint-1 @low-priority @A23
  Scenario: Extent config update includes previously excluded border features
    Given the spatial extent northern latitude boundary is "37.10"
    When a client requests items from the "water_wells" layer
    Then the response includes the feature with id "4826"
    And that feature's latitude is between "37.00" and "37.10"

  @backend @ogc-geometry @sprint-1 @low-priority @A23
  Scenario: Extent config update does not modify feature data for existing layers
    Given the geometry and attributes of feature "4826" from "water_wells" are recorded as a baseline
    And the spatial extent northern latitude boundary is "37.10"
    When a client requests the feature with id "4826" from the "water_wells" layer
    Then the feature geometry coordinates match the recorded baseline
    And the feature attributes match the recorded baseline
