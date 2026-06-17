#!/bin/sh
# Start Postgres with pg_cron preloaded and its scheduler pointed at the
# application database. cron.database_name is derived from POSTGRES_DB so that,
# when the image is run with POSTGRES_DB overridden, pg_cron watches the same
# database the app (and the alembic migration) connects to.
set -e

exec docker-entrypoint.sh postgres \
    -c shared_preload_libraries=pg_cron \
    -c "cron.database_name=${POSTGRES_DB:-ocotilloapi}"
