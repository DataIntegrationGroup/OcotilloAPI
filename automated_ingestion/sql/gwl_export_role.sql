-- Read-only Postgres grants for the groundwater level export (OCO-79).
--
-- The `gwl-export-<env>` Cloud Run job reads public groundwater levels and
-- nothing else. It writes no rows anywhere: its output goes to GCS. Run by
-- hand as a superuser against the *primary* -- grants replicate to the read
-- replica the job actually connects to.
--
-- As with ingestion_role.sql, the role already exists once Terraform registers
-- the service account as a Cloud SQL IAM user (google_sql_user.gwl_export), so
-- this only grants:
--
--   psql "host=... dbname=ocotillo user=postgres" \
--     -v db_name=ocotillo \
--     -v role_name=ocotillo-gwl-export@waterdatainitiative-271000.iam \
--     -f automated_ingestion/sql/gwl_export_role.sql

\if :{?db_name}
\else
\echo 'ERROR: pass -v db_name=<database>. The instance hosts more than one.'
\quit
\endif

\if :{?role_name}
\else
\echo 'ERROR: pass -v role_name=<role>.'
\quit
\endif

GRANT CONNECT ON DATABASE :"db_name" TO :"role_name";
GRANT USAGE ON SCHEMA public TO :"role_name";

-- Exactly the tables in automated_ingestion/exports/groundwater_levels/
-- snapshot.py. A new join there needs a line here, or the snapshot step fails
-- with a permission error naming the table.
GRANT SELECT ON
    observation,
    parameter,
    sample,
    field_activity,
    field_event,
    thing,
    location,
    location_thing_association
TO :"role_name";

-- Belt and braces: the snapshot transaction is already READ ONLY, and the
-- replica refuses writes, but the role should not be able to write either.
ALTER ROLE :"role_name" SET default_transaction_read_only = on;
