-- ============================================================================
-- OcotilloAPI Database Schema Dump
-- PostgreSQL 17 with PostGIS Extension
-- ============================================================================
-- This file contains the complete database schema for OcotilloAPI
-- Use this to recreate the database structure on a new instance
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE VOCABULARY TABLES
-- ============================================================================

-- Lexicon Categories
CREATE TABLE lexicon_category (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- Lexicon Terms (Controlled Vocabulary)
CREATE TABLE lexicon_term (
    id SERIAL PRIMARY KEY,
    term VARCHAR NOT NULL UNIQUE,
    definition VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- Lexicon Term-Category Association
CREATE TABLE lexicon_term_category_association (
    id SERIAL PRIMARY KEY,
    term_id INTEGER NOT NULL REFERENCES lexicon_term(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES lexicon_category(id) ON DELETE CASCADE
);

-- Lexicon Triples (Semantic Relationships)
CREATE TABLE lexicon_triple (
    id SERIAL PRIMARY KEY,
    subject VARCHAR(100) REFERENCES lexicon_term(term) ON DELETE CASCADE,
    predicate VARCHAR(100),
    object_ VARCHAR(100) REFERENCES lexicon_term(term) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- ============================================================================
-- GEOGRAPHIC & REFERENCE DATA
-- ============================================================================

-- Locations (Geographic Points)
CREATE TABLE location (
    id SERIAL PRIMARY KEY,
    nma_pk_location VARCHAR(36),
    description VARCHAR,
    point GEOMETRY(POINT, 4326),
    elevation FLOAT,
    county VARCHAR(100),
    state VARCHAR(100),
    quad_name VARCHAR(100),
    nma_notes_location TEXT,
    nma_coordinate_notes TEXT,
    nma_date_created DATE,
    nma_site_date DATE,
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    search_vector TSVECTOR
);

CREATE INDEX idx_location_point ON location USING GIST (point);
CREATE INDEX idx_location_search ON location USING GIN (search_vector);

-- Aquifer Systems
CREATE TABLE aquifer_system (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    description TEXT,
    primary_aquifer_type VARCHAR(100) REFERENCES lexicon_term(term),
    geographic_scale VARCHAR(100) REFERENCES lexicon_term(term),
    boundary GEOMETRY(MULTIPOLYGON, 4326),
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

CREATE INDEX idx_aquifer_system_name ON aquifer_system(name);
CREATE INDEX idx_aquifer_system_boundary ON aquifer_system USING GIST (boundary);

-- Geologic Formations
CREATE TABLE geologic_formation (
    id SERIAL PRIMARY KEY,
    formation_code VARCHAR(100) UNIQUE REFERENCES lexicon_term(term),
    description TEXT,
    lithology VARCHAR(100) REFERENCES lexicon_term(term),
    boundary GEOMETRY(MULTIPOLYGON, 4326),
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

CREATE INDEX idx_geologic_formation_code ON geologic_formation(formation_code);
CREATE INDEX idx_geologic_formation_boundary ON geologic_formation USING GIST (boundary);

-- ============================================================================
-- THING (Well/Spring/Stream Gauge)
-- ============================================================================

CREATE TABLE thing (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    thing_type VARCHAR REFERENCES lexicon_term(term),
    first_visit_date DATE,
    nma_pk_welldata VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),

    -- Well-specific columns
    well_depth FLOAT,
    hole_depth FLOAT,
    well_casing_diameter FLOAT,
    well_casing_depth FLOAT,
    well_completion_date DATE,
    well_driller_name VARCHAR(200),
    well_construction_method VARCHAR REFERENCES lexicon_term(term),
    well_pump_type VARCHAR REFERENCES lexicon_term(term),
    well_pump_depth FLOAT,
    formation_completion_code VARCHAR REFERENCES lexicon_term(term),
    is_suitable_for_datalogger BOOLEAN,

    -- Spring-specific columns
    spring_type VARCHAR REFERENCES lexicon_term(term),

    -- Audit columns
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    search_vector TSVECTOR
);

CREATE INDEX idx_thing_search ON thing USING GIN (search_vector);

-- Location-Thing Association (Time-Series)
CREATE TABLE location_thing_association (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES location(id),
    thing_id INTEGER NOT NULL REFERENCES thing(id),
    effective_start TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    effective_end TIMESTAMP WITH TIME ZONE
);

-- Well Screens
CREATE TABLE well_screen (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    aquifer_system_id INTEGER REFERENCES aquifer_system(id) ON DELETE SET NULL,
    geologic_formation_id INTEGER REFERENCES geologic_formation(id) ON DELETE SET NULL,
    screen_depth_top FLOAT,
    screen_depth_bottom FLOAT,
    screen_type VARCHAR(100) REFERENCES lexicon_term(term),
    screen_description VARCHAR(1000),
    nma_pk_wellscreens VARCHAR(100),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Well Purpose
CREATE TABLE well_purpose (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    purpose VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_well_purpose_search ON well_purpose USING GIN (search_vector);

-- Well Casing Material
CREATE TABLE well_casing_material (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    material VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_well_casing_material_search ON well_casing_material USING GIN (search_vector);

-- Thing Aquifer Association
CREATE TABLE thing_aquifer_association (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    aquifer_system_id INTEGER NOT NULL REFERENCES aquifer_system(id) ON DELETE CASCADE,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Aquifer Type
CREATE TABLE aquifer_type (
    id SERIAL PRIMARY KEY,
    thing_aquifer_association_id INTEGER NOT NULL REFERENCES thing_aquifer_association(id) ON DELETE CASCADE,
    aquifer_type VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Thing Geologic Formation Association
CREATE TABLE thing_geologic_formation_association (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    geologic_formation_id INTEGER REFERENCES geologic_formation(id) ON DELETE SET NULL,
    top_depth FLOAT NOT NULL,
    bottom_depth FLOAT NOT NULL,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Thing ID Links (External System IDs)
CREATE TABLE thing_id_link (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    relation VARCHAR(100) REFERENCES lexicon_term(term),
    alternate_id VARCHAR(100),
    alternate_organization VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Measuring Point History
CREATE TABLE measuring_point_history (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    measuring_point_height NUMERIC NOT NULL,
    measuring_point_description TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    reason TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Monitoring Frequency History
CREATE TABLE monitoring_frequency_history (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    monitoring_frequency VARCHAR(100) REFERENCES lexicon_term(term),
    start_date DATE NOT NULL,
    end_date DATE,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- ============================================================================
-- CONTACTS & ORGANIZATIONS
-- ============================================================================

CREATE TABLE contact (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    organization VARCHAR(100) REFERENCES lexicon_term(term),
    role VARCHAR(100) REFERENCES lexicon_term(term),
    contact_type VARCHAR(100) REFERENCES lexicon_term(term),
    nma_pk_owners VARCHAR(100),
    nma_pk_waterlevels VARCHAR(100),
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    search_vector TSVECTOR,
    CONSTRAINT uq_contact_name_organization UNIQUE (name, organization)
);

CREATE INDEX idx_contact_search ON contact USING GIN (search_vector);

-- Phone Numbers
CREATE TABLE phone (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    phone_number VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_phone_search ON phone USING GIN (search_vector);

-- Email Addresses
CREATE TABLE email (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    email VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_email_search ON email USING GIN (search_vector);

-- Physical Addresses
CREATE TABLE address (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    street VARCHAR,
    city VARCHAR,
    state VARCHAR,
    zip_code VARCHAR,
    country VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_address_search ON address USING GIN (search_vector);

-- Incomplete NMA Phone (legacy migration support)
CREATE TABLE incomplete_nma_phone (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    phone_number VARCHAR
);

-- Thing-Contact Association
CREATE TABLE thing_contact_association (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER REFERENCES thing(id),
    contact_id INTEGER REFERENCES contact(id)
);

-- ============================================================================
-- SENSORS & EQUIPMENT
-- ============================================================================

CREATE TABLE sensor (
    id SERIAL PRIMARY KEY,
    nma_pk_equipment VARCHAR(36),
    name VARCHAR(255) NOT NULL,
    sensor_type VARCHAR(100) REFERENCES lexicon_term(term),
    model VARCHAR(50),
    serial_no VARCHAR(50) UNIQUE,
    pcn_number VARCHAR(50) UNIQUE,
    owner_agency VARCHAR(100) REFERENCES lexicon_term(term),
    sensor_status VARCHAR(100) REFERENCES lexicon_term(term),
    notes TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- Sensor Deployments
CREATE TABLE deployment (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    sensor_id INTEGER NOT NULL REFERENCES sensor(id),
    installation_date DATE NOT NULL,
    removal_date DATE,
    recording_interval INTEGER,
    recording_interval_units VARCHAR(100) REFERENCES lexicon_term(term),
    hanging_cable_length NUMERIC,
    hanging_point_height NUMERIC,
    hanging_point_description TEXT,
    notes TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- ============================================================================
-- PARAMETERS & ANALYSIS
-- ============================================================================

CREATE TABLE parameter (
    id SERIAL PRIMARY KEY,
    parameter_name VARCHAR(100) REFERENCES lexicon_term(term),
    matrix VARCHAR(100) REFERENCES lexicon_term(term),
    parameter_type VARCHAR(100) REFERENCES lexicon_term(term),
    cas_number VARCHAR,
    default_unit VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    CONSTRAINT uq_parameter_name_matrix UNIQUE (parameter_name, matrix)
);

CREATE TABLE analysis_method (
    id SERIAL PRIMARY KEY,
    analysis_method_code VARCHAR UNIQUE,
    analysis_method_name VARCHAR,
    analysis_method_type VARCHAR(100) REFERENCES lexicon_term(term),
    source_organization VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE TABLE regulatory_limit (
    id SERIAL PRIMARY KEY,
    parameter_id INTEGER NOT NULL REFERENCES parameter(id),
    limit_source VARCHAR(100) REFERENCES lexicon_term(term),
    limit_value NUMERIC NOT NULL,
    limit_unit VARCHAR(100) REFERENCES lexicon_term(term),
    limit_type VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- ============================================================================
-- FIELD ACTIVITIES & SAMPLING
-- ============================================================================

CREATE TABLE field_event (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    event_date TIMESTAMP WITH TIME ZONE NOT NULL,
    notes TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE TABLE field_event_participant (
    id SERIAL PRIMARY KEY,
    field_event_id INTEGER NOT NULL REFERENCES field_event(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    participant_role VARCHAR(100) REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE TABLE field_activity (
    id SERIAL PRIMARY KEY,
    field_event_id INTEGER NOT NULL REFERENCES field_event(id) ON DELETE CASCADE,
    activity_type VARCHAR(100) REFERENCES lexicon_term(term),
    notes TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE TABLE sample (
    id SERIAL PRIMARY KEY,
    field_activity_id INTEGER NOT NULL REFERENCES field_activity(id) ON DELETE CASCADE,
    field_event_participant_id VARCHAR REFERENCES field_event_participant(id),
    sample_date TIMESTAMP WITH TIME ZONE NOT NULL,
    sample_name VARCHAR NOT NULL UNIQUE,
    sample_matrix VARCHAR(100) REFERENCES lexicon_term(term),
    sample_method VARCHAR(100) REFERENCES lexicon_term(term),
    qc_type VARCHAR DEFAULT 'Normal',
    depth_top FLOAT,
    depth_bottom FLOAT,
    notes TEXT,
    nma_pk_waterlevels VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

CREATE TABLE observation (
    id SERIAL PRIMARY KEY,
    nma_pk_waterlevels VARCHAR,
    sample_id INTEGER NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
    sensor_id INTEGER REFERENCES sensor(id),
    analysis_method_id INTEGER REFERENCES analysis_method(id),
    parameter_id INTEGER NOT NULL REFERENCES parameter(id),
    observation_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    value FLOAT,
    unit VARCHAR(100) REFERENCES lexicon_term(term),
    notes TEXT,
    measuring_point_height FLOAT,
    groundwater_level_reason VARCHAR REFERENCES lexicon_term(term),
    release_status VARCHAR REFERENCES lexicon_term(term),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255)
);

-- ============================================================================
-- TRANSDUCER (Continuous Monitoring)
-- ============================================================================

CREATE TABLE transducer_observation_block (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE,
    parameter_id INTEGER NOT NULL REFERENCES parameter(id) ON DELETE CASCADE,
    review_status VARCHAR(100) REFERENCES lexicon_term(term),
    start_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    end_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    comment TEXT,
    reviewer_id VARCHAR REFERENCES contact(id) ON DELETE CASCADE,
    CONSTRAINT uq_transducer_block_thing_status_parameter_time UNIQUE (thing_id, review_status, parameter_id, start_datetime, end_datetime),
    CONSTRAINT ck_transducer_block_end_after_start CHECK (end_datetime > start_datetime)
);

CREATE INDEX idx_transducer_block_thing ON transducer_observation_block(thing_id);
CREATE INDEX idx_transducer_block_parameter ON transducer_observation_block(parameter_id);
CREATE INDEX idx_transducer_block_time ON transducer_observation_block(start_datetime, end_datetime);

CREATE TABLE transducer_observation (
    id SERIAL PRIMARY KEY,
    parameter_id INTEGER NOT NULL REFERENCES parameter(id) ON DELETE CASCADE,
    deployment_id INTEGER NOT NULL REFERENCES deployment(id) ON DELETE CASCADE,
    observation_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    value FLOAT NOT NULL,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE INDEX idx_transducer_observation_datetime ON transducer_observation(observation_datetime);
CREATE INDEX idx_transducer_observation_parameter ON transducer_observation(parameter_id);

-- ============================================================================
-- GROUPS & PROJECTS
-- ============================================================================

CREATE TABLE "group" (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(255),
    project_area GEOMETRY(MULTIPOLYGON, 4326),
    group_type VARCHAR(100) REFERENCES lexicon_term(term),
    parent_group_id INTEGER REFERENCES "group"(id),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE INDEX idx_group_project_area ON "group" USING GIST (project_area);

CREATE TABLE group_thing_association (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES "group"(id) ON DELETE CASCADE,
    thing_id INTEGER NOT NULL REFERENCES thing(id) ON DELETE CASCADE
);

-- ============================================================================
-- ASSETS (File Storage)
-- ============================================================================

CREATE TABLE asset (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    label VARCHAR,
    storage_service VARCHAR,
    storage_path VARCHAR,
    mime_type VARCHAR,
    size INTEGER,
    uri VARCHAR,
    release_status VARCHAR REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_asset_search ON asset USING GIN (search_vector);

CREATE TABLE asset_thing_association (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES asset(id) ON DELETE CASCADE,
    thing_id INTEGER REFERENCES thing(id) ON DELETE CASCADE
);

-- ============================================================================
-- PUBLICATIONS & AUTHORS
-- ============================================================================

CREATE TABLE pub_author (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    affiliation VARCHAR,
    search_vector TSVECTOR
);

CREATE INDEX idx_pub_author_search ON pub_author USING GIN (search_vector);

CREATE TABLE publication (
    id SERIAL PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    doi VARCHAR UNIQUE,
    year INTEGER,
    publisher VARCHAR,
    url VARCHAR,
    publication_type VARCHAR(100) REFERENCES lexicon_term(term),
    search_vector TSVECTOR
);

CREATE INDEX idx_publication_search ON publication USING GIN (search_vector);

CREATE TABLE pub_author_contact_association (
    author_id INTEGER REFERENCES pub_author(id),
    contact_id INTEGER REFERENCES contact(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    PRIMARY KEY (author_id, contact_id)
);

CREATE TABLE pub_author_publication_association (
    publication_id INTEGER REFERENCES publication(id),
    author_id INTEGER REFERENCES pub_author(id),
    author_order INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    created_by_name VARCHAR(255),
    created_by_id VARCHAR(255),
    updated_by_name VARCHAR(255),
    updated_by_id VARCHAR(255),
    PRIMARY KEY (publication_id, author_id)
);

-- ============================================================================
-- POLYMORPHIC TABLES
-- ============================================================================

-- Status History (for Thing, Location, etc.)
CREATE TABLE status_history (
    id SERIAL PRIMARY KEY,
    status_type VARCHAR(100) REFERENCES lexicon_term(term),
    status_value VARCHAR(100) REFERENCES lexicon_term(term),
    start_date DATE NOT NULL,
    end_date DATE,
    reason TEXT,
    target_id INTEGER,
    target_table VARCHAR(50),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- Notes (for Thing, Location, etc.)
CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    target_id INTEGER,
    target_table VARCHAR,
    note_type VARCHAR(100) REFERENCES lexicon_term(term),
    content TEXT,
    release_status VARCHAR REFERENCES lexicon_term(term)
);

CREATE INDEX idx_notes_polymorphic_link ON notes(target_id, target_table);

-- Data Provenance (for Thing, Location, etc.)
CREATE TABLE data_provenance (
    id SERIAL PRIMARY KEY,
    target_id INTEGER,
    target_table VARCHAR,
    field_name VARCHAR,
    origin_type VARCHAR(100) REFERENCES lexicon_term(term),
    origin_source VARCHAR,
    collection_method VARCHAR(100) REFERENCES lexicon_term(term),
    accuracy_value FLOAT,
    accuracy_unit VARCHAR(100) REFERENCES lexicon_term(term)
);

CREATE INDEX idx_provenance_targets ON data_provenance(target_id, target_table);

-- Permission History
CREATE TABLE permission_history (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    permission_type VARCHAR(100) REFERENCES lexicon_term(term),
    permission_allowed BOOLEAN DEFAULT false,
    start_date DATE NOT NULL,
    end_date DATE,
    notes TEXT,
    target_id INTEGER,
    target_table VARCHAR(50),
    release_status VARCHAR REFERENCES lexicon_term(term)
);

-- ============================================================================
-- LEGACY SUPPORT TABLES
-- ============================================================================

CREATE TABLE geochronology_age (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES location(id),
    age FLOAT,
    age_error FLOAT,
    method VARCHAR(100) REFERENCES lexicon_term(term)
);

CREATE TABLE collaborative_network_well (
    id SERIAL PRIMARY KEY,
    thing_id INTEGER REFERENCES thing(id),
    actively_monitored BOOLEAN
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE thing IS 'Physical monitoring locations (wells, springs, stream gauges)';
COMMENT ON TABLE location IS 'Geographic coordinates and metadata for sites';
COMMENT ON TABLE observation IS 'Individual measurements from samples or sensors';
COMMENT ON TABLE sample IS 'Samples collected during field activities';
COMMENT ON TABLE parameter IS 'Controlled vocabulary for measurable properties';
COMMENT ON TABLE sensor IS 'Equipment inventory for data collection devices';
COMMENT ON TABLE deployment IS 'Installation history of sensors at things';
COMMENT ON TABLE lexicon_term IS 'Controlled vocabulary terms';
COMMENT ON TABLE contact IS 'People and organizations';
COMMENT ON TABLE field_event IS 'Field visits to monitoring locations';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
