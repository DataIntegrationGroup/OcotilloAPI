-- Initialize test database inside the same Postgres service used for dev.
-- This script runs only when the data directory is first initialized.

CREATE DATABASE ocotilloapi_test;

\connect ocotilloapi_dev
CREATE EXTENSION IF NOT EXISTS postgis;

\connect ocotilloapi_test
CREATE EXTENSION IF NOT EXISTS postgis;
