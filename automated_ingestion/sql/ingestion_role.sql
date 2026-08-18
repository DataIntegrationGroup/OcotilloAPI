-- Least-privilege Postgres role for the automated ingestion pipeline.
--
-- Run by hand against each environment as a superuser. Not an Alembic
-- migration: roles and grants are per-environment infrastructure, not schema,
-- and migrations run under this database's application role rather than a
-- superuser.
--
-- The point of the role is blast radius. The pipeline writes observations and
-- the reference rows they hang from, and reads everything it must resolve
-- against. It cannot touch chemistry, contacts, assets, or the legacy NMA_*
-- and NMW_* tables, so a bug in an adapter cannot corrupt data no ingestion
-- path should ever reach.

-- Set the password out of band; do not commit it. It belongs in Secret
-- Manager alongside internal-ogc-api-keys.
--   CREATE ROLE ocotillo_ingestion LOGIN PASSWORD '...';
--
-- Or, preferred, use IAM database authentication and create the role for the
-- service account instead, so there is no password to rotate:
--   CREATE ROLE "ocotillo-ingestion@PROJECT.iam" WITH LOGIN;
--   GRANT cloudsqliamuser TO "ocotillo-ingestion@PROJECT.iam";

\set role_name ocotillo_ingestion

GRANT CONNECT ON DATABASE :"db_name" TO :"role_name";
GRANT USAGE ON SCHEMA public TO :"role_name";

-- Written: the observations themselves and the rows a new series needs.
GRANT SELECT, INSERT, UPDATE ON
    transducer_observation,
    transducer_observation_block,
    deployment,
    sensor,
    parameter
TO :"role_name";

-- `parameter` is versioned by sqlalchemy-continuum, so an insert there also
-- writes a version row and a transaction row. Without these two grants the
-- write fails at runtime with a permission error on a table the code never
-- names directly -- an unpleasant thing to debug.
GRANT SELECT, INSERT ON parameter_version, transaction TO :"role_name";

-- Read-only: resolved against, never written. `thing` and `location` are
-- deliberately not writable. Reconciling the 33 San Acacia wells means
-- matching them to rows that already exist; if reconciliation finds a well
-- missing, that is a decision for a human, not a row the pipeline invents.
GRANT SELECT ON
    thing,
    thing_id_link,
    location,
    lexicon_term,
    lexicon_category,
    lexicon_term_category_association
TO :"role_name";

-- Inserts need the sequences behind the autoincrement primary keys.
GRANT USAGE, SELECT ON SEQUENCE
    transducer_observation_id_seq,
    transducer_observation_block_id_seq,
    deployment_id_seq,
    sensor_id_seq,
    parameter_id_seq,
    transaction_id_seq
TO :"role_name";

-- No default privileges are granted. A table added later is invisible to this
-- role until someone grants it deliberately, which is the intended failure
-- mode: a new table reaching the pipeline should be a decision.
