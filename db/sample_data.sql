-- ============================================================================
-- OcotilloAPI Sample Data
-- ============================================================================
-- This file contains sample data to populate a new OcotilloAPI instance
-- Run this AFTER running schema_dump.sql and initializing lexicon/parameters
-- ============================================================================

-- Prerequisites:
-- 1. PostGIS extension must be enabled
-- 2. Lexicon terms must be initialized (via core/lexicon.json)
-- 3. Parameters must be initialized (via core/parameter.json)

BEGIN;

-- ============================================================================
-- SAMPLE CONTACTS
-- ============================================================================

INSERT INTO contact (id, name, organization, role, contact_type, release_status, created_at)
VALUES
    (1, 'John Smith', 'USGS', 'Hydrologist', 'person', 'public', NOW()),
    (2, 'Jane Doe', 'New Mexico Bureau of Geology', 'Field Technician', 'person', 'public', NOW()),
    (3, 'Robert Johnson', 'NM Environment Department', 'Water Quality Specialist', 'person', 'public', NOW()),
    (4, 'Maria Garcia', 'Los Alamos National Laboratory', 'Environmental Scientist', 'person', 'public', NOW()),
    (5, 'David Chen', 'Sandia National Laboratories', 'Geologist', 'person', 'public', NOW());

-- Set sequence to continue from last ID
SELECT setval('contact_id_seq', 5);

-- Contact Emails
INSERT INTO email (contact_id, email, release_status)
VALUES
    (1, 'john.smith@usgs.gov', 'public'),
    (2, 'jane.doe@nmbg.nmt.edu', 'public'),
    (3, 'robert.johnson@env.nm.gov', 'public'),
    (4, 'maria.garcia@lanl.gov', 'public'),
    (5, 'david.chen@sandia.gov', 'public');

-- Contact Phones
INSERT INTO phone (contact_id, phone_number, release_status)
VALUES
    (1, '505-123-4567', 'public'),
    (2, '575-234-5678', 'public'),
    (3, '505-345-6789', 'public'),
    (4, '505-456-7890', 'public'),
    (5, '505-567-8901', 'public');

-- Contact Addresses
INSERT INTO address (contact_id, street, city, state, zip_code, country, release_status)
VALUES
    (1, '5338 Montgomery Blvd NE', 'Albuquerque', 'NM', '87109', 'USA', 'public'),
    (2, '801 Leroy Place', 'Socorro', 'NM', '87801', 'USA', 'public'),
    (3, '1190 Saint Francis Dr', 'Santa Fe', 'NM', '87505', 'USA', 'public'),
    (4, 'TA-3, SM-29', 'Los Alamos', 'NM', '87545', 'USA', 'public'),
    (5, '1515 Eubank Blvd SE', 'Albuquerque', 'NM', '87123', 'USA', 'public');

-- ============================================================================
-- SAMPLE LOCATIONS (New Mexico coordinates)
-- ============================================================================

INSERT INTO location (id, description, point, elevation, county, state, release_status, created_at)
VALUES
    (1, 'Albuquerque East Mesa', ST_SetSRID(ST_MakePoint(-106.5419, 35.1107), 4326), 1620.5, 'Bernalillo', 'NM', 'public', NOW()),
    (2, 'Santa Fe Buckman Well Field', ST_SetSRID(ST_MakePoint(-106.0031, 35.7381), 4326), 1850.2, 'Santa Fe', 'NM', 'public', NOW()),
    (3, 'Las Cruces East Mesa', ST_SetSRID(ST_MakePoint(-106.7369, 32.3199), 4326), 1220.8, 'Dona Ana', 'NM', 'public', NOW()),
    (4, 'Los Alamos Canyon', ST_SetSRID(ST_MakePoint(-106.3198, 35.8869), 4326), 2134.6, 'Los Alamos', 'NM', 'public', NOW()),
    (5, 'Carlsbad Caverns Area', ST_SetSRID(ST_MakePoint(-104.4457, 32.1476), 4326), 1095.3, 'Eddy', 'NM', 'public', NOW());

SELECT setval('location_id_seq', 5);

-- ============================================================================
-- SAMPLE AQUIFER SYSTEMS
-- ============================================================================

INSERT INTO aquifer_system (id, name, description, primary_aquifer_type, geographic_scale, release_status, created_at)
VALUES
    (1, 'Santa Fe Group Aquifer System', 'Basin-fill aquifer underlying the Rio Grande rift', 'unconfined', 'major', 'public', NOW()),
    (2, 'Ogallala Aquifer', 'High Plains aquifer in eastern New Mexico', 'unconfined', 'major', 'public', NOW()),
    (3, 'Roswell Artesian Basin', 'Confined aquifer in Pecos River valley', 'confined', 'regional', 'public', NOW());

SELECT setval('aquifer_system_id_seq', 3);

-- ============================================================================
-- SAMPLE GEOLOGIC FORMATIONS
-- ============================================================================

INSERT INTO geologic_formation (id, formation_code, description, lithology, release_status, created_at)
VALUES
    (1, 'alluvium', 'Quaternary alluvial deposits', 'alluvium', 'public', NOW()),
    (2, 'santa fe group', 'Tertiary basin-fill sediments', 'sandstone', 'public', NOW()),
    (3, 'bandelier tuff', 'Volcanic tuff from Valles Caldera', 'tuff', 'public', NOW());

SELECT setval('geologic_formation_id_seq', 3);

-- ============================================================================
-- SAMPLE SENSORS
-- ============================================================================

INSERT INTO sensor (id, name, sensor_type, model, serial_no, pcn_number, owner_agency, sensor_status, release_status, created_at)
VALUES
    (1, 'Pressure Transducer PT-001', 'pressure transducer', 'In-Situ Level TROLL 500', 'SN123456', 'PCN-2024-001', 'USGS', 'in service', 'public', NOW()),
    (2, 'Barometer BAR-001', 'barometer', 'In-Situ Baro TROLL', 'SN789012', 'PCN-2024-002', 'USGS', 'in service', 'public', NOW()),
    (3, 'Acoustic Probe AC-001', 'acoustic probe', 'Solinst Model 107', 'SN345678', 'PCN-2024-003', 'NMBG', 'in service', 'public', NOW()),
    (4, 'Electric Tape ET-001', 'electric tape', 'Solinst Model 101', 'SN901234', 'PCN-2024-004', 'NMED', 'in service', 'public', NOW()),
    (5, 'Water Level Logger WL-001', 'water level logger', 'Onset HOBO U20L', 'SN567890', 'PCN-2024-005', 'LANL', 'in service', 'public', NOW());

SELECT setval('sensor_id_seq', 5);

-- ============================================================================
-- SAMPLE THINGS (Wells)
-- ============================================================================

INSERT INTO thing (id, name, thing_type, well_depth, hole_depth, well_casing_diameter, well_casing_depth,
                   well_completion_date, well_driller_name, is_suitable_for_datalogger, release_status, created_at)
VALUES
    (1, 'ABQ-EAST-001', 'water well', 350.0, 365.0, 6.0, 340.0, '2015-06-15', 'ABC Drilling Company', true, 'public', NOW()),
    (2, 'SF-BUCKMAN-042', 'water well', 800.0, 825.0, 12.0, 780.0, '2010-03-22', 'New Mexico Well Drilling', true, 'public', NOW()),
    (3, 'LC-MESA-108', 'water well', 450.0, 465.0, 8.0, 440.0, '2018-11-08', 'Southwest Drilling Inc', true, 'public', NOW()),
    (4, 'LA-CANYON-019', 'water well', 280.0, 295.0, 6.0, 270.0, '2012-08-30', 'Mountain Drilling LLC', false, 'public', NOW()),
    (5, 'CARLSBAD-055', 'water well', 520.0, 535.0, 10.0, 500.0, '2020-01-17', 'Pecos Valley Drilling', true, 'public', NOW());

SELECT setval('thing_id_seq', 5);

-- Link Things to Locations (with current effective dates)
INSERT INTO location_thing_association (location_id, thing_id, effective_start, effective_end)
VALUES
    (1, 1, NOW(), NULL),
    (2, 2, NOW(), NULL),
    (3, 3, NOW(), NULL),
    (4, 4, NOW(), NULL),
    (5, 5, NOW(), NULL);

-- ============================================================================
-- WELL DETAILS
-- ============================================================================

-- Well Purposes
INSERT INTO well_purpose (thing_id, purpose, release_status)
VALUES
    (1, 'monitoring', 'public'),
    (2, 'public supply', 'public'),
    (3, 'monitoring', 'public'),
    (4, 'monitoring', 'public'),
    (5, 'monitoring', 'public');

-- Well Casing Materials
INSERT INTO well_casing_material (thing_id, material, release_status)
VALUES
    (1, 'steel', 'public'),
    (2, 'steel', 'public'),
    (3, 'pvc', 'public'),
    (4, 'steel', 'public'),
    (5, 'steel', 'public');

-- Well Screens
INSERT INTO well_screen (thing_id, aquifer_system_id, geologic_formation_id, screen_depth_top, screen_depth_bottom,
                         screen_type, screen_description, release_status)
VALUES
    (1, 1, 2, 320.0, 350.0, 'slotted', '30 ft slotted screen in Santa Fe Group', 'public'),
    (2, 1, 2, 750.0, 800.0, 'slotted', '50 ft slotted screen in Santa Fe Group', 'public'),
    (3, 1, 1, 420.0, 450.0, 'slotted', '30 ft slotted screen in alluvium', 'public'),
    (4, 1, 3, 250.0, 280.0, 'slotted', '30 ft slotted screen in Bandelier Tuff', 'public'),
    (5, 3, 1, 490.0, 520.0, 'slotted', '30 ft slotted screen in Roswell Basin', 'public');

-- Thing-Aquifer Associations
INSERT INTO thing_aquifer_association (thing_id, aquifer_system_id, release_status)
VALUES
    (1, 1, 'public'),
    (2, 1, 'public'),
    (3, 1, 'public'),
    (4, 1, 'public'),
    (5, 3, 'public');

-- Aquifer Types for each association
INSERT INTO aquifer_type (thing_aquifer_association_id, aquifer_type, release_status)
VALUES
    (1, 'unconfined', 'public'),
    (2, 'unconfined', 'public'),
    (3, 'unconfined', 'public'),
    (4, 'fractured', 'public'),
    (5, 'confined', 'public');

-- Measuring Point History (current)
INSERT INTO measuring_point_history (thing_id, measuring_point_height, measuring_point_description, start_date, end_date, release_status)
VALUES
    (1, 2.5, 'Top of casing, 2.5 ft above ground surface', '2015-06-15', NULL, 'public'),
    (2, 3.0, 'Top of casing, 3.0 ft above ground surface', '2010-03-22', NULL, 'public'),
    (3, 2.0, 'Top of casing, 2.0 ft above ground surface', '2018-11-08', NULL, 'public'),
    (4, 1.5, 'Top of casing, 1.5 ft above ground surface', '2012-08-30', NULL, 'public'),
    (5, 2.8, 'Top of casing, 2.8 ft above ground surface', '2020-01-17', NULL, 'public');

-- Monitoring Frequency History
INSERT INTO monitoring_frequency_history (thing_id, monitoring_frequency, start_date, end_date, release_status)
VALUES
    (1, 'quarterly', '2015-06-15', NULL, 'public'),
    (2, 'monthly', '2010-03-22', NULL, 'public'),
    (3, 'quarterly', '2018-11-08', NULL, 'public'),
    (4, 'annual', '2012-08-30', NULL, 'public'),
    (5, 'quarterly', '2020-01-17', NULL, 'public');

-- Thing-Contact Associations (well ownership/access)
INSERT INTO thing_contact_association (thing_id, contact_id)
VALUES
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5);

-- ============================================================================
-- SAMPLE DEPLOYMENTS
-- ============================================================================

INSERT INTO deployment (thing_id, sensor_id, installation_date, removal_date, recording_interval,
                        recording_interval_units, hanging_cable_length, release_status, created_at)
VALUES
    (1, 1, '2024-01-15', NULL, 15, 'minutes', 325.0, 'public', NOW()),
    (2, 3, '2024-02-20', NULL, 60, 'minutes', 785.0, 'public', NOW()),
    (3, 1, '2024-03-10', '2024-06-10', 30, 'minutes', 445.0, 'public', NOW()),
    (4, 5, '2024-04-05', NULL, 30, 'minutes', 275.0, 'public', NOW()),
    (5, 1, '2024-05-01', NULL, 15, 'minutes', 515.0, 'public', NOW());

-- ============================================================================
-- SAMPLE FIELD EVENTS & SAMPLING
-- ============================================================================

-- Field Events (site visits)
INSERT INTO field_event (id, thing_id, event_date, notes, release_status)
VALUES
    (1, 1, '2024-06-15 10:30:00+00', 'Quarterly monitoring event', 'public'),
    (2, 2, '2024-06-18 09:00:00+00', 'Monthly water level measurement', 'public'),
    (3, 3, '2024-06-20 14:15:00+00', 'Quarterly sampling and water level', 'public'),
    (4, 4, '2024-06-22 11:00:00+00', 'Annual inspection and measurement', 'public'),
    (5, 5, '2024-06-25 08:30:00+00', 'Quarterly monitoring', 'public');

SELECT setval('field_event_id_seq', 5);

-- Field Event Participants
INSERT INTO field_event_participant (id, field_event_id, contact_id, participant_role, release_status)
VALUES
    (1, 1, 1, 'field technician', 'public'),
    (2, 2, 2, 'field technician', 'public'),
    (3, 3, 3, 'sampler', 'public'),
    (4, 4, 4, 'field technician', 'public'),
    (5, 5, 5, 'field technician', 'public');

SELECT setval('field_event_participant_id_seq', 5);

-- Field Activities
INSERT INTO field_activity (id, field_event_id, activity_type, notes, release_status)
VALUES
    (1, 1, 'water level measurement', 'Measured depth to water', 'public'),
    (2, 2, 'water level measurement', 'Measured depth to water', 'public'),
    (3, 3, 'water quality sampling', 'Collected sample for metals analysis', 'public'),
    (4, 4, 'water level measurement', 'Annual monitoring measurement', 'public'),
    (5, 5, 'water level measurement', 'Quarterly monitoring', 'public');

SELECT setval('field_activity_id_seq', 5);

-- Samples
INSERT INTO sample (id, field_activity_id, field_event_participant_id, sample_date, sample_name,
                    sample_matrix, sample_method, qc_type, release_status, created_at)
VALUES
    (1, 1, '1', '2024-06-15 10:45:00+00', 'ABQ-EAST-001-20240615', 'water', 'bailer', 'Normal', 'public', NOW()),
    (2, 2, '2', '2024-06-18 09:15:00+00', 'SF-BUCKMAN-042-20240618', 'water', 'electric tape', 'Normal', 'public', NOW()),
    (3, 3, '3', '2024-06-20 14:30:00+00', 'LC-MESA-108-20240620', 'water', 'bailer', 'Normal', 'public', NOW()),
    (4, 4, '4', '2024-06-22 11:15:00+00', 'LA-CANYON-019-20240622', 'water', 'electric tape', 'Normal', 'public', NOW()),
    (5, 5, '5', '2024-06-25 08:45:00+00', 'CARLSBAD-055-20240625', 'water', 'bailer', 'Normal', 'public', NOW());

SELECT setval('sample_id_seq', 5);

-- ============================================================================
-- SAMPLE OBSERVATIONS (Water Levels)
-- ============================================================================
-- Note: This assumes parameter IDs exist from initialization
-- Common water parameter IDs: 1=depth to water, 2=water temperature, 3=pH, etc.

INSERT INTO observation (sample_id, parameter_id, observation_datetime, value, unit,
                         measuring_point_height, release_status, created_at)
VALUES
    -- Depth to water observations
    (1, 1, '2024-06-15 10:45:00+00', 145.32, 'feet', 2.5, 'public', NOW()),
    (2, 1, '2024-06-18 09:15:00+00', 287.56, 'feet', 3.0, 'public', NOW()),
    (3, 1, '2024-06-20 14:30:00+00', 178.91, 'feet', 2.0, 'public', NOW()),
    (4, 1, '2024-06-22 11:15:00+00', 98.44, 'feet', 1.5, 'public', NOW()),
    (5, 1, '2024-06-25 08:45:00+00', 223.67, 'feet', 2.8, 'public', NOW()),

    -- Water temperature observations
    (1, 2, '2024-06-15 10:45:00+00', 15.8, 'celsius', NULL, 'public', NOW()),
    (2, 2, '2024-06-18 09:15:00+00', 14.2, 'celsius', NULL, 'public', NOW()),
    (3, 2, '2024-06-20 14:30:00+00', 16.5, 'celsius', NULL, 'public', NOW()),
    (4, 2, '2024-06-22 11:15:00+00', 13.9, 'celsius', NULL, 'public', NOW()),
    (5, 2, '2024-06-25 08:45:00+00', 17.1, 'celsius', NULL, 'public', NOW());

-- ============================================================================
-- SAMPLE GROUPS/PROJECTS
-- ============================================================================

INSERT INTO "group" (id, name, description, group_type, release_status)
VALUES
    (1, 'Albuquerque Basin Monitoring Network', 'Long-term monitoring of groundwater levels in Albuquerque Basin', 'monitoring network', 'public'),
    (2, 'Santa Fe Basin Study', 'Water resources assessment for Santa Fe Basin', 'research project', 'public'),
    (3, 'Statewide Baseline Network', 'Wells monitored for baseline water quality', 'monitoring network', 'public');

SELECT setval('group_id_seq', 3);

INSERT INTO group_thing_association (group_id, thing_id)
VALUES
    (1, 1),
    (1, 3),
    (2, 2),
    (2, 4),
    (3, 1),
    (3, 2),
    (3, 3),
    (3, 4),
    (3, 5);

-- ============================================================================
-- SAMPLE NOTES
-- ============================================================================

INSERT INTO notes (target_id, target_table, note_type, content, release_status)
VALUES
    (1, 'thing', 'general', 'Well is located on public land. Easy access via maintained road.', 'public'),
    (2, 'thing', 'construction', 'Well drilled using air rotary method. Casing is cemented to surface.', 'public'),
    (3, 'thing', 'sampling procedure', 'Purge 3 well volumes before sampling. Use low-flow sampling method.', 'public'),
    (4, 'thing', 'general', 'Well is on LANL property. Requires security clearance for access.', 'public'),
    (5, 'thing', 'water quality', 'Historical elevated nitrate levels detected. Monitor quarterly.', 'public');

-- ============================================================================
-- SAMPLE DATA PROVENANCE
-- ============================================================================

INSERT INTO data_provenance (target_id, target_table, field_name, origin_type, origin_source, collection_method, accuracy_value, accuracy_unit)
VALUES
    (1, 'location', 'point', 'GPS', 'Field survey 2015-06-15', 'gps survey grade', 0.5, 'meters'),
    (1, 'location', 'elevation', 'GPS', 'Field survey 2015-06-15', 'gps survey grade', 0.3, 'meters'),
    (2, 'location', 'point', 'GPS', 'Field survey 2010-03-22', 'gps survey grade', 0.5, 'meters'),
    (3, 'location', 'point', 'GPS', 'Field survey 2018-11-08', 'gps handheld', 3.0, 'meters'),
    (1, 'thing', 'well_depth', 'drillers log', 'ABC Drilling Company completion report', NULL, NULL, NULL);

-- ============================================================================
-- SAMPLE STATUS HISTORY
-- ============================================================================

INSERT INTO status_history (status_type, status_value, start_date, end_date, target_id, target_table, release_status)
VALUES
    ('well status', 'active', '2015-06-15', NULL, 1, 'thing', 'public'),
    ('monitoring status', 'routine monitoring', '2015-06-15', NULL, 1, 'thing', 'public'),
    ('well status', 'active', '2010-03-22', NULL, 2, 'thing', 'public'),
    ('monitoring status', 'routine monitoring', '2010-03-22', NULL, 2, 'thing', 'public'),
    ('well status', 'active', '2018-11-08', NULL, 3, 'thing', 'public');

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================
-- Run these to verify data was inserted correctly:

-- SELECT COUNT(*) as contact_count FROM contact;
-- SELECT COUNT(*) as location_count FROM location;
-- SELECT COUNT(*) as thing_count FROM thing;
-- SELECT COUNT(*) as sensor_count FROM sensor;
-- SELECT COUNT(*) as observation_count FROM observation;
-- SELECT COUNT(*) as sample_count FROM sample;
-- SELECT COUNT(*) as deployment_count FROM deployment;

-- List all wells with their locations:
-- SELECT t.name, l.county, l.state, ST_AsText(l.point) as coordinates
-- FROM thing t
-- JOIN location_thing_association lta ON t.id = lta.thing_id
-- JOIN location l ON lta.location_id = l.id
-- WHERE lta.effective_end IS NULL;

-- ============================================================================
-- END OF SAMPLE DATA
-- ============================================================================
