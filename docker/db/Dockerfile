# Production database image: PostGIS + pg_cron.
#
# This image is intentionally NOT used by the development docker-compose
# service (which runs the stock postgis/postgis image). pg_cron is a
# production-only dependency required by the nightly materialized-view refresh
# job registered in alembic migration x2y3z4a5b6c7.
#
# pg_cron must be loaded via shared_preload_libraries, and its background
# worker schedules jobs in a single database (cron.database_name). Both are set
# below so the alembic-registered job runs against the application database.
#
# Build/run example:
#   docker build -f docker/db/Dockerfile -t ocotillo-db-prod .
#   docker run -e POSTGRES_DB=ocotilloapi ocotillo-db-prod
#
# On Google Cloud SQL, pg_cron is enabled via the cloudsql.enable_pg_cron flag
# instead of this image; see docs/pg_cron-nightly-refresh.md.
FROM postgis/postgis:17-3.5

# Install the pg_cron extension for PostgreSQL 17.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-cron \
    && rm -rf /var/lib/apt/lists/*

# Load pg_cron at server start and point its scheduler at the application
# database. cron.database_name is derived from POSTGRES_DB at start time (see
# start-postgres.sh) so it stays aligned even when POSTGRES_DB is overridden.
ENV POSTGRES_DB=ocotilloapi
COPY docker/db/start-postgres.sh /usr/local/bin/start-postgres.sh
RUN chmod +x /usr/local/bin/start-postgres.sh
ENTRYPOINT ["start-postgres.sh"]
