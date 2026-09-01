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
| `thing_type` | Literal `'water well'` — the view's row filter |
| `release_status` | `thing.release_status` |
| `nma_pk_welldata` | `thing.nma_pk_welldata` |
| `alternate_ids` | `thing_id_link.alternate_organization` + `.alternate_id`, comma-joined |
| `county` | `location.county`, most recent association |
| `state` | `location.state`, most recent association |
| `quad_name` | `location.quad_name`, most recent association |
| `latitude` | `ST_Y(location.point)` — decimal degrees, WGS 84 |
| `longitude` | `ST_X(location.point)` — decimal degrees, WGS 84 |
| `elevation` | `location.elevation`, most recent association |
| `elevation_method` | `data_provenance.collection_method` where `target_table = 'location'` and `field_name = 'elevation'`, latest `id` |
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
| `nma_formation_zone` | `thing.nma_formation_zone` |
| `well_purposes` | `well_purpose.purpose`, comma-joined |
| `well_casing_materials` | `well_casing_material.material`, comma-joined |
| `screen_count` | `count(well_screen)` |
| `screen_depth_top` | `min(well_screen.screen_depth_top)` |
| `screen_depth_bottom` | `max(well_screen.screen_depth_bottom)` |
| `measuring_point_height` | `measuring_point_history.measuring_point_height`, current record |
| `measuring_point_description` | `measuring_point_history.measuring_point_description`, current record |
| `measuring_point_start_date` | `measuring_point_history.start_date`, current record |
| `well_status` | `status_history.status_value` where `status_type = 'Well Status'`, current record |
| `well_status_since` | `status_history.start_date`, same record |
| `monitoring_status` | `status_history.status_value` where `status_type = 'Monitoring Status'`, current record |
| `monitoring_status_since` | `status_history.start_date`, same record |
| `monitoring_status_reason` | `status_history.reason`, same record |
| `access_status` | `status_history.status_value` where `status_type = 'Access Status'`, current record |
| `access_status_since` | `status_history.start_date`, same record |
| `open_status` | `status_history.status_value` where `status_type = 'Open Status'`, current record |
| `open_status_since` | `status_history.start_date`, same record |
| `datalogger_suitability_status` | `status_history.status_value` where `status_type = 'Datalogger Suitability Status'`, current record |
| `datalogger_suitability_status_since` | `status_history.start_date`, same record |
| `may_measure_water_level` | `permission_history.permission_allowed` where `permission_type = 'Water Level Sample'`, current record |
| `may_sample_water_chemistry` | `permission_history.permission_allowed` where `permission_type = 'Water Chemistry Sample'`, current record |
| `may_install_datalogger` | `permission_history.permission_allowed` where `permission_type = 'Datalogger Installation'`, current record |
| `permission_granted_by` | `contact.name` via `permission_history.contact_id` on the current water-level grant |
| `monitoring_frequency` | `monitoring_frequency_history.monitoring_frequency`, current record |
| `monitoring_frequency_since` | `monitoring_frequency_history.start_date`, current record |
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
| `field_event_last_date` | `max(field_event.event_date)`, UTC date *(stats)* |
| `has_datalogger` | `true` when an open logger deployment exists — see `datalogger_sensor_type` |
| `datalogger_deployment_count` | `count(deployment)` open logger deployments |
| `datalogger_sensor_type` | `sensor.sensor_type` on the current deployment, restricted to Data Logger / Pressure Transducer / DiverLink / Diver Cable |
| `datalogger_model` | `sensor.model`, same deployment |
| `datalogger_serial_no` | `sensor.serial_no`, same deployment |
| `datalogger_sensor_status` | `sensor.sensor_status`, same deployment |
| `datalogger_installed_date` | `deployment.installation_date`, same deployment |
| `datalogger_recording_interval` | `deployment.recording_interval`, same deployment |
| `datalogger_recording_interval_units` | `deployment.recording_interval_units`, same deployment |
| `datalogger_hanging_point_description` | `deployment.hanging_point_description`, same deployment |
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
| `point` | `location.point`, most recent association (PostGIS Point, EPSG:4326) |
