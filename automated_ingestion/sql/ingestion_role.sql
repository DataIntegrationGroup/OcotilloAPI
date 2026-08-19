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

-- IAM authentication is the configured path, and the reason is that it removes
-- the credential rather than rotating it: Cloud SQL mints a short-lived token
-- from the service account, so there is no password to store anywhere.
--
-- **The role already exists.** Registering the service account as a Cloud SQL
-- IAM user creates the Postgres role automatically -- Terraform does that via
-- google_sql_user.ingestion. Confirmed with:
--
--   gcloud sql users list --instance=dataservices
--   ...
--   ocotillo-ingestion@waterdatainitiative-271000.iam  CLOUD_IAM_SERVICE_ACCOUNT
--
-- So this script only grants. Do not add a CREATE ROLE: it would fail, and
-- reaching for one is a sign the Terraform half has not been applied.
--
-- Run it as a superuser, passing both names -- nothing is hardcoded, because
-- the instance hosts `ocotillo` and `ocotillo-staging` and running the wrong
-- one is silent:
--
--   psql "host=... dbname=ocotillo user=postgres" \
--     -v db_name=ocotillo \
--     -v role_name=ocotillo-ingestion@waterdatainitiative-271000.iam \
--     -f automated_ingestion/sql/ingestion_role.sql
--
-- The role name has an @ and dots, so every reference below uses :"role_name",
-- which quotes it as an identifier. An unquoted one is a syntax error.
--
-- Password authentication, if IAM is ever unavailable: create the role by hand,
-- store the password in Secret Manager, set CLOUD_SQL_IAM_AUTH=0, and pass
-- -v role_name=ocotillo_ingestion instead.

\if :{?db_name}
\else
\echo 'ERROR: pass -v db_name=<database>. The instance hosts more than one.'
\quit
\endif

\if :{?role_name}
\else
\echo 'ERROR: pass -v role_name=<role>. See the header for the IAM role name.'
\quit
\endif

\echo 'Granting to' :"role_name" 'on' :"db_name"

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
