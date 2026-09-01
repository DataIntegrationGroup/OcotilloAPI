# water well field operations — column sources

Every column published by `ogc_internal_water_well_field_operations`, in view
order, and where its value comes from. Columns marked *(stats)* are read from
the `ogc_internal_water_well_field_operations_stats` materialized view and are as
fresh as its last refresh; everything else is joined live on each request.

"Current record" means the history row satisfying
`start_date <= CURRENT_DATE AND (end_date IS NULL OR end_date >= CURRENT_DATE)`,
latest `start_date` first. "Most recent association" means the
`location_thing_association` row with no `effective_end`, latest
`effective_start` first.

Generated from the view definition in
`alembic/versions/e1f2a3b4c5d6_add_water_well_field_operations_layer.py`. Field
prose lives in `core/ogc-field-descriptions.yml`; the design rationale lives in
`docs/water-well-field-operations-layer.md`.

| Column | Source |
| --- | --- |
| `id` | `thing.id` |
| `name` | `thing.name` |
| `station_type` | Literal `'water well'` — the view's row filter. Named `station_type` rather than `thing_type` to match the naming already established on the public thing-type views |
| `release_status` | `thing.release_status` |
| `alternate_ids` | `thing_id_link.alternate_organization` + `.alternate_id`, comma-joined |
| `latitude` | `ST_Y(location.point)` — decimal degrees, WGS 84 |
| `longitude` | `ST_X(location.point)` — decimal degrees, WGS 84 |
| `elevation` | `location.elevation`, most recent association |
| `well_depth` | `thing.well_depth` |
| `hole_depth` | `thing.hole_depth` |
| `well_casing_diameter` | `thing.well_casing_diameter` |
| `well_casing_depth` | `thing.well_casing_depth` |
| `well_completion_date` | `thing.well_completion_date` |
| `well_driller_name` | `thing.well_driller_name` |
| `well_construction_method` | `thing.well_construction_method` |
| `well_pump_type` | `thing.well_pump_type` |
| `well_pump_depth` | `thing.well_pump_depth` |
| `formation_completion_code` | `thing.formation_completion_code` |
| `formation_completion_description` | `lexicon_term.definition` where `term = thing.formation_completion_code`. Neither this nor `aquifer_system_name` below is date-windowed — neither source table carries a `start_date`/`end_date` |
| `well_purpose` | `well_purpose.purpose`, comma-joined |
| `well_casing_material` | `well_casing_material.material`, comma-joined |
| `aquifer_system_name` | `aquifer_system.name` via `thing_aquifer_association`, comma-joined |
| `screen_count` | `count(well_screen)` |
| `screen_depth_top` | `well_screen.screen_depth_top`, every interval, semicolon-joined, ordered shallowest first, `COALESCE(..., '')` for the same reason as the equipment columns |
| `screen_depth_bottom` | `well_screen.screen_depth_bottom`, same intervals, same order, same `COALESCE(..., '')` treatment |
| `screen_description` | `well_screen.screen_description`, same intervals, same order, same `COALESCE(..., '')` treatment |
| `mp_height` | `measuring_point_history.measuring_point_height`, current record |
| `mp_description` | `measuring_point_history.measuring_point_description`, current record |
| `well_status` | `status_history.status_value` where `status_type = 'Well Status'`, current record |
| `monitoring_status` | `status_history.status_value` where `status_type = 'Monitoring Status'`, current record |
| `open_status` | `status_history.status_value` where `status_type = 'Open Status'`, current record |
| `datalogger_suitability_status` | `status_history.status_value` where `status_type = 'Datalogger Suitability Status'`, current record |
| `may_measure_water_level` | `permission_history.permission_allowed` where `permission_type = 'Water Level Sample'`, current record |
| `may_sample_water_chemistry` | `permission_history.permission_allowed` where `permission_type = 'Water Chemistry Sample'`, current record |
| `may_install_datalogger` | `permission_history.permission_allowed` where `permission_type = 'Datalogger Installation'`, current record |
| `permission_granted_by` | `contact.name` via `permission_history.contact_id` on the current water-level grant |
| `monitoring_frequency` | `monitoring_frequency_history.monitoring_frequency`, current record |
| `group_names` | `group.name` via `group_thing_association`, comma-joined |
| `group_types` | `group.group_type`, same order as `group_names` |
| `manual_water_level_count` | `count(observation)` via `sample` → `field_activity` → `field_event`, `activity_type = 'groundwater level'` *(stats)* |
| `manual_water_level_first_date` | `min(observation.observation_datetime)`, UTC date, same chain *(stats)* |
| `manual_water_level_last_date` | `max(observation.observation_datetime)`, UTC date, same chain *(stats)* |
| `days_since_manual_water_level` | `CURRENT_DATE - manual_water_level_last_date` |
| `last_depth_to_water_ft` | `observation.value - COALESCE(observation.measuring_point_height, 0)` on the latest reading *(stats)* |
| `chemistry_sample_count` | `count(DISTINCT sample.id)`, `activity_type = 'water chemistry'` *(stats)* |
| `chemistry_sample_last_date` | `max(sample.sample_date)`, UTC date, same filter *(stats)* |
| `days_since_chemistry_sample` | `CURRENT_DATE - chemistry_sample_last_date` |
| `field_event_count` | `count(field_event)` for the well *(stats)* |
| `date_last_visited` | `max(field_event.event_date)`, UTC date *(stats, column named `field_event_last_date` there)* |
| `has_datalogger` | `true` when a currently-installed deployment exists whose `sensor.sensor_type` is Data Logger / Pressure Transducer / DiverLink / Diver Cable. Stays logger-scoped even though the columns below do not |
| `datalogger_deployment_count` | `count(deployment)`, same logger-only filter as `has_datalogger` |
| `sensor_type` | `sensor.sensor_type` for every currently-installed deployment (`installation_date IS NOT NULL AND removal_date IS NULL`), **any sensor type, not just loggers** — semicolon-joined, ordered by `sensor_type` |
| `model` | `sensor.model`, same deployments, same order as `sensor_type`. `COALESCE(..., '')` before aggregating, so a null value is an empty segment, not a dropped position |
| `serial_no` | `sensor.serial_no`, same deployments, same order, same `COALESCE(..., '')` treatment |
| `sensor_status` | `sensor.sensor_status`, same deployments, same order, same `COALESCE(..., '')` treatment |
| `installed_date` | `deployment.installation_date`, same deployments, same order. In practice never null -- `installed_deployments` filters on `installation_date IS NOT NULL` -- but `COALESCE`d anyway for consistency with its siblings |
| `recording_interval` | `deployment.recording_interval`, same deployments, same order, same `COALESCE(..., '')` treatment — `text`, not `integer`, because `string_agg` produces `text` regardless of how many deployments a given well has |
| `recording_interval_units` | `deployment.recording_interval_units`, same deployments, same order, same `COALESCE(..., '')` treatment |
| `hanging_point_desc` | `deployment.hanging_point_description`, same deployments, same order, same `COALESCE(..., '')` treatment |
| `continuous_reading_count` | `count(transducer_observation)` via `deployment` *(stats)* |
| `continuous_first_datetime` | `min(transducer_observation.observation_datetime)` *(stats)* |
| `continuous_last_datetime` | `max(transducer_observation.observation_datetime)` *(stats)* |
| `days_since_continuous_reading` | `CURRENT_DATE - continuous_last_datetime::date` |
| `contact_count` | `count(DISTINCT contact)` via `thing_contact_association` |
| `primary_contact_name` | `contact.name`, `contact_type = 'Primary'` preferred, else lowest `contact.id` |
| `primary_contact_organization` | `contact.organization`, same contact |
| `primary_contact_role` | `contact.role`, same contact |
| `primary_contact_type` | `contact.contact_type`, same contact — says whether the row above is a real primary or a fallback |
| `primary_contact_phone` | `phone.phone_number`, lowest `phone.id` for that contact |
| `primary_contact_email` | `email.email`, lowest `email.id` for that contact |
| `contact_names` | `contact.name` for every associated contact, comma-joined |
| `access_notes` | `notes.content` where `note_type = 'Access'`, newest first, joined with ` | ` |
| `directions_notes` | `notes.content` where `note_type = 'Directions'`, newest first, joined with ` | ` |
| `communication_notes` | `notes.content` where `note_type = 'Communication'`, newest first, joined with ` | ` |
| `construction_notes` | `notes.content` where `note_type = 'Construction'`, newest first, joined with ` | ` |
| `maintenance_notes` | `notes.content` where `note_type = 'Maintenance'`, newest first, joined with ` | ` |
| `historical_notes` | `notes.content` where `note_type = 'Historical'`, newest first, joined with ` | ` |
| `general_notes` | `notes.content` where `note_type = 'General'`, newest first, joined with ` | ` |
| `water_notes` | `notes.content` where `note_type = 'Water'`, newest first, joined with ` | ` |
| `water_quality_notes` | `notes.content` where `note_type = 'Water Quality'`, newest first, joined with ` | ` |
| `sampling_procedure_notes` | `notes.content` where `note_type = 'Sampling Procedure'`, newest first, joined with ` | ` |
| `coordinate_notes` | `notes.content` where `note_type = 'Coordinate'`, newest first, joined with ` | ` |
| `owner_comment_notes` | `notes.content` where `note_type = 'OwnerComment'`, newest first, joined with ` | ` |
| `site_notes_legacy` | `notes.content` where `note_type = 'Site Notes (legacy)'`, newest first, joined with ` | `. Not `site_notes_legacy_notes` — the lexicon term already says "notes" |
| `point` | `location.point`, most recent association (PostGIS Point, EPSG:4326) |
