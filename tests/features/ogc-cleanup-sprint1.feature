Feature: OGC Feature Layer Cleanup — Sprint 1
  As an OGC API consumer
  I want the Ocotillo API feature layers to be accurately filtered, correctly named, and reliably configured
  So that I can depend on the API for scientific and operational use

  # Sprint 1 scope: A1, A2, A3, A4, A6, A11, A13, A16, A17, A18, A22, A23
  # Sprint 2 scope: A7, A8, A10, A14, A20
  # Sprint 3 scope: A9, A12, A21
  # Sprint 4 scope: A5, A15
  #
  # Not included:
  #   A19 — Hide sparse Group A layers from the public catalog. The ticket's
  #         Acceptance Criteria say to remove the layers, but its Sprint/Epic
  #         field reads "keep sparse groups" instead of a sprint number,
  #         which contradicts that guidance. Left out of this feature file
  #         until the conflict is resolved in the ticket.

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
  # A5 — Address int(None) runtime warning in pygeoapi itemtypes
  # ---------------------------------------------------------------------------

  @backend @ogc-infrastructure @sprint-4 @high-priority @A5
  Scenario: Items requests no longer emit the int(None) runtime warning
    Given the A5 null guard has been applied to pygeoapi/api/itemtypes.py
    When a client requests items from the water_wells layer
    Then the server logs contain no int(None) runtime warning

  @backend @ogc-infrastructure @sprint-4 @high-priority @A5
  Scenario: Items response content is unaffected by the null guard fix
    Given the A5 null guard has been applied to pygeoapi/api/itemtypes.py
    When a client requests items from the water_wells layer
    Then the response HTTP status is 200
    And the response Content-Type is "application/geo+json"

  # ---------------------------------------------------------------------------
  # A7 — Implement Level 1 naming pass across all layers
  # ---------------------------------------------------------------------------

  @backend @ogc-naming @sprint-2 @high-priority @A7
  Scenario: Display titles are updated for layers with a naming defect
    Given the Level 1 naming pass has been applied
    When a client requests /ogcapi/collections
    Then the display title for each of the following layers matches its proposed title
      | layer-id                         | title                                     |
      | diversions_surface_water         | Surface Water Diversions                  |
      | lakes_ponds_reservoirs           | Lakes and Reservoirs                      |
      | outfalls_wastewater_return_flow  | Wastewater Outfalls                       |
      | latest_tds_wells                 | Water Well Latest Total Dissolved Solids  |
      | major_chemistry_results          | Water Well Major Chemistry                |

  @backend @ogc-naming @sprint-2 @high-priority @A7
  Scenario: Layer ids are unchanged by the Level 1 naming pass
    Given the Level 1 naming pass has been applied
    When a client requests /ogcapi/collections
    Then each of the following layers keeps its pre-naming-pass id
      | layer-id                         |
      | diversions_surface_water         |
      | lakes_ponds_reservoirs           |
      | outfalls_wastewater_return_flow  |
      | latest_tds_wells                 |
      | major_chemistry_results          |
      | actively_monitored_wells         |

  # ---------------------------------------------------------------------------
  # A8 — Decide and implement Level 2 or Level 3 ID renames
  # ---------------------------------------------------------------------------

  # A8 policy gate: the team must decide Level 2 (grace period with
  # deprecated aliases) or Level 3 (immediate rename) per Section 6.2.1
  # before implementation begins. Tracked in ticket — not enforced as a
  # Behave scenario.

  # No outside organizations had access to the API before the renames, so
  # no need for a grace period. The renames will be implemented as
  # Level 3 (immediate) renames.

  @backend @ogc-naming @sprint-2 @high-priority @A8
  Scenario Outline: A substantive rename is discoverable under its proposed id
    Given the team has decided on a rename level for the substantive renames
    When the layer previously known as "<current-id>" is renamed to "<proposed-id>"
    Then a client requesting items from "<proposed-id>" receives that layer's features

    Examples:
      | current-id                       | proposed-id                               |
      | diversions_surface_water         | surface_water_diversions                  |
      | lakes_ponds_reservoirs           | lakes_and_reservoirs                      |
      | outfalls_wastewater_return_flow  | wastewater_outfalls                       |
      | latest_tds_wells                 | water_well_latest_total_dissolved_solids  |
      | major_chemistry_results          | water_well_major_chemistry                |

  @backend @ogc-naming @sprint-2 @high-priority @A8
  Scenario: Old collection id returns deprecation headers during a Level 2 grace period
    Given the team decided on Level 2 renames with a 90-day grace period
    When a client requests items from a layer under its old id
    Then the response includes Deprecation, Sunset, and Link headers
    And the response still returns that layer's features

  @backend @ogc-naming @sprint-2 @high-priority @A8
  Scenario: Old collection id is removed immediately under a Level 3 rename
    Given the team decided on Level 3 renames with no grace period
    When a client requests items from a layer under its old id
    Then the response HTTP status is 404

  # ---------------------------------------------------------------------------
  # A9 — Define the publication predicate per layer family
  # ---------------------------------------------------------------------------

  # A9 is a governance action, not an engineering task: a named data owner
  # must document, for each layer family (thing-based, chemistry and
  # water-level, group-based, monitoring), which combination of
  # release_status values, parent records, and joined tables must all be
  # public before a feature is safe to serve. The document is reviewed and
  # stored in the project knowledge base. A10 cannot begin correctly until
  # this is complete. Tracked in ticket — not enforced as a Behave scenario.

  # ---------------------------------------------------------------------------
  # A10 — Implement more permanent per-layer SQL filters
  # ---------------------------------------------------------------------------

  @backend @ogc-exposure @sprint-2 @high-priority @A10 @migration-mutates-schema @cleanup_samples
  Scenario: Water elevation layer excludes a well whose only water level observation is non-public
    Given a well has release_status "public" but its only water level observation has release_status "private"
    And a second well has release_status "public" and its only water level observation has release_status "public"
    When a client requests items from the water_elevation_wells layer
    Then the response does not include the well with the private observation
    And the response includes the well with the public observation

  @backend @ogc-exposure @sprint-2 @high-priority @A10 @migration-mutates-schema @cleanup_samples
  Scenario: project_areas exposure follows the owning group's release_status
    Given a project_areas group has release_status "public"
    When a client requests items from the project_areas layer
    Then the polygon feature for that group is included in the response

  @backend @ogc-exposure @sprint-2 @high-priority @A10 @cleanup_samples
  Scenario: Known private and draft records remain excluded after the permanent filter is applied
    Given known private and draft feature ids are seeded in each layer family
    When a client requests items from each of those layers
    Then none of the seeded private or draft feature ids appear in the response

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
  # A12 — Null out sentinel dates in chemistry layer matviews
  # ---------------------------------------------------------------------------

  @backend @ogc-data-currency @sprint-3 @medium-priority @A12 @migration-mutates-schema @cleanup_samples
  Scenario Outline: Sentinel sample dates are nulled out after the matview migration
    Given a record in "<layer-id>" has a sample date of "1900-01-01"
    When the A12 migration is applied and the matview is refreshed
    Then that record's sample date is null

    Examples:
      | layer-id                 |
      | major_chemistry_results  |
      | minor_chemistry_wells    |
      | latest_tds_wells         |

  @backend @ogc-data-currency @sprint-3 @medium-priority @A12 @migration-mutates-schema @cleanup_samples
  Scenario Outline: Valid historical sample dates are unaffected by the sentinel date fix
    Given a record in "<layer-id>" has a sample date of "1998-04-12"
    When the A12 migration is applied and the matview is refreshed
    Then that record's sample date is still "1998-04-12"

    Examples:
      | layer-id                 |
      | major_chemistry_results  |
      | minor_chemistry_wells    |
      | latest_tds_wells         |

  @backend @ogc-data-currency @sprint-3 @medium-priority @A12
  Scenario: Layer descriptions document the sentinel date convention
    When a client requests /ogcapi/collections
    Then the description for each of the following layers states that a null sample date means the date is unknown
      | layer-id                 |
      | major_chemistry_results  |
      | minor_chemistry_wells    |
      | latest_tds_wells         |

  # ---------------------------------------------------------------------------
  # A13 — Add last_observation_date column to Group A view template
  # ---------------------------------------------------------------------------

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13 @production
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

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13 @production
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

  @backend @ogc-data-currency @sprint-1 @medium-priority @A13 @production
  Scenario: Consumers can filter Group A layers by last_observation_date
    Given each of the following Group A layers has features with last_observation_date values "2019-06-01" and "2023-06-01":
      | layer-id                        |
      | water_wells                     |
      | springs                         |
      | perennial_streams               |
      | meteorological_stations         |
      | ephemeral_streams                |
      | rock_sample_locations            |
      | diversions_surface_water         |
      | lakes_ponds_reservoirs           |
      | soil_gas_sample_locations        |
      | outfalls_wastewater_return_flow  |
    When a client requests items from each of those layers with filter
      """
      last_observation_date > '2021-01-01'
      """
    Then only features with a last_observation_date of "2023-06-01" are returned from each layer
    # other_things is not listed: it is in the Group A view template, but A18
    # took it off the public catalog — it is only reachable on /ogcapi-internal.

  # ---------------------------------------------------------------------------
  # A14 — Split Group A view template into well and non-well variants
  # ---------------------------------------------------------------------------

  @backend @ogc-naming @sprint-2 @medium-priority @A14 @migration-mutates-schema
  Scenario Outline: Non-well Group A layers no longer expose well-specific columns
    Given the Group A view template has been split into well and non-well variants
    When a client requests items from "<layer-id>"
    Then the feature properties do not include the following well-specific columns
      | column                |
      | well_depth            |
      | well_completion_date  |
      | well_casing_diameter  |

    Examples:
      | layer-id                         |
      | springs                          |
      | perennial_streams                |
      | meteorological_stations          |
      | ephemeral_streams                |
      | rock_sample_locations            |
      | diversions_surface_water         |
      | lakes_ponds_reservoirs           |
      | soil_gas_sample_locations        |
      | outfalls_wastewater_return_flow  |

  @backend @ogc-naming @sprint-2 @medium-priority @A14 @migration-mutates-schema
  Scenario: Well layer keeps its well-specific columns after the template split
    Given the Group A view template has been split into well and non-well variants
    When a client requests items from the water_wells layer
    Then the feature properties include well_depth

  # ---------------------------------------------------------------------------
  # A15 — Document and verify materialized view refresh schedule
  # ---------------------------------------------------------------------------

  # A15's runbook documentation and refresh cadence (daily for water-level
  # matviews, weekly for chemistry matviews, as a starting baseline) are
  # tracked in ticket — not enforced as a Behave scenario. The scenario below
  # covers the one system-observable outcome: a refresh job is actually
  # running.

  @backend @ogc-data-currency @sprint-4 @medium-priority @A15
  Scenario Outline: Group B materialized views have a recent refresh timestamp
    Given a scheduled refresh job has been configured for the Group B materialized views
    When the database schema is inspected
    Then the last refresh timestamp for "<layer-id>" is within its documented refresh cadence

    Examples:
      | layer-id                     |
      | water_well_summary           |
      | depth_to_water_trend_wells   |
      | water_elevation_wells        |
      | latest_depth_to_water_wells  |
      | avg_tds_wells                |
      | major_chemistry_results      |
      | minor_chemistry_wells        |

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
  # A20 — Extend OGC test coverage to all 22 layers with a release_status regression test
  # ---------------------------------------------------------------------------

  # Related to decisions needed for permissions strategy - not going to do (8/25/2026).

  @backend @ogc-infrastructure @sprint-2 @medium-priority @A20
  Scenario: Every configured collection is discoverable in the public catalog
    When a client requests /ogcapi/collections
    Then the response includes all of the following 18 collection ids
      | layer-id                        |
      | water_wells                     |
      | springs                         |
      | perennial_streams                |
      | meteorological_stations         |
      | ephemeral_streams                |
      | rock_sample_locations            |
      | diversions_surface_water         |
      | lakes_ponds_reservoirs           |
      | soil_gas_sample_locations        |
      | outfalls_wastewater_return_flow  |
      | water_well_summary               |
      | depth_to_water_trend_wells       |
      | water_elevation_wells            |
      | major_chemistry_results          |
      | minor_chemistry_wells            |
      | latest_tds_wells                 |
      | actively_monitored_wells         |
      | project_areas                    |

  @backend @ogc-infrastructure @sprint-2 @medium-priority @A20 @cleanup_samples
  Scenario Outline: A known private record is excluded from public items by feature id
    Given a feature with id "<feature-id>" in "<layer-id>" has release_status "private"
    When a client requests items from "<layer-id>"
    Then no returned feature has id "<feature-id>"

    Examples:
      | layer-id                 | feature-id |
      | water_wells               | 7734       |
      | major_chemistry_results   | 8102       |

  @backend @ogc-infrastructure @sprint-2 @medium-priority @A20 @cleanup_samples
  Scenario Outline: A known draft record is excluded from public items by feature id
    Given a feature with id "<feature-id>" in "<layer-id>" has release_status "draft"
    When a client requests items from "<layer-id>"
    Then no returned feature has id "<feature-id>"

    Examples:
      | layer-id       | feature-id |
      | water_wells     | 7735       |
      | project_areas   | 19         |

  # ---------------------------------------------------------------------------
  # A21 — Create separate database roles for public and internal OGC access
  # ---------------------------------------------------------------------------

  @backend @ogc-infrastructure @sprint-3 @medium-priority @A21
  Scenario: Public database role has no privilege on internal OGC relations
    Given the public read-only database role has been created
    When the role's grants are inspected
    Then the role has SELECT privilege only on the public ogc_* views
    And the role has no privilege on any ogc_internal_ relation

  @backend @ogc-infrastructure @sprint-3 @medium-priority @A21
  Scenario: Internal database role has SELECT privilege on internal OGC views
    Given the internal read-only database role has been created
    When the role's grants are inspected
    Then the role has SELECT privilege on the ogc_internal_ views

  @backend @ogc-infrastructure @sprint-3 @medium-priority @A21
  Scenario: A misrouted request to internal relations fails closed under the public role
    Given the /ogcapi public mount is connected to the database as the public read-only role
    When the public mount is misconfigured to query an ogc_internal_ relation
    Then the database denies the query with a permission error
    And no rows are returned

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
