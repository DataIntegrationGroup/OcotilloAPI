# Nightly materialized-view refresh with pg_cron

Every materialized view in the database (the `ogc_*` pygeoapi views and
`transducer_daily_data`) is refreshed once a night in production by a
[pg_cron](https://github.com/citusdata/pg_cron) job.

## What is registered, and where

Alembic migration
[`x2y3z4a5b6c7_schedule_nightly_matview_refresh_pg_cron.py`](../alembic/versions/x2y3z4a5b6c7_schedule_nightly_matview_refresh_pg_cron.py)
registers everything, so the schedule is traceable in version control:

- A SQL helper, `public.refresh_pygeoapi_materialized_views()`, that discovers
  every materialized view in the public schema from the catalog at run time and
  runs `REFRESH MATERIALIZED VIEW` for each (plain, non-concurrent — see note).
- A pg_cron job named `refresh-pygeoapi-materialized-views` that runs
  `SELECT public.refresh_pygeoapi_materialized_views();` on the schedule
  `0 9 * * *` (09:00 in the **server timezone**, UTC on Cloud SQL and the
  production image — roughly 02:00–03:00 US Mountain).

The helper refreshes whatever materialized views exist, so a view added by a
later migration is picked up automatically — there is nothing to keep in sync
and no need to reschedule. (The `oco refresh-pygeoapi-materialized-views` CLI
command, used for manual/on-deploy refreshes, keeps an explicit list in
[`services/materialized_views.py`](../services/materialized_views.py).)
To change the schedule, edit the migration (or add a new one). Do not edit the
job in the database by hand, or it will drift from the repo.

## Why it is gated by `ENABLE_PG_CRON`

pg_cron is a **production-only** dependency. It must be loaded through the
server's `shared_preload_libraries`, which the development docker-compose
Postgres image (`postgis/postgis:17-3.5`) does not do. Running
`CREATE EXTENSION pg_cron` without that preload fails.

So the migration is a **no-op unless `ENABLE_PG_CRON` is truthy**:

- Development, test, CI, **and staging**: `ENABLE_PG_CRON` unset → migration
  prints a skip message and records itself as applied. `alembic upgrade head`
  works on the stock dev image with nothing extra installed. Staging refreshes
  the views on each deploy instead (the "Refresh materialized views" CD step),
  so it does not need the nightly job.
- Production: `ENABLE_PG_CRON=1` → migration creates the extension, the helper
  function, and the cron job. Only `CD_production.yml` sets this.

## Production setup

### Self-hosted / Docker

Use the production database image, which installs pg_cron and preloads it:

- [`docker/db/Dockerfile`](../docker/db/Dockerfile) installs
  `postgresql-17-cron` and starts Postgres with
  `-c shared_preload_libraries=pg_cron -c cron.database_name=$POSTGRES_DB`
  (via [`start-postgres.sh`](../docker/db/start-postgres.sh), so overriding
  `POSTGRES_DB` keeps the scheduler pointed at the same database).

`cron.database_name` must match the application database so the alembic
migration (which connects to that database) can `CREATE EXTENSION pg_cron` and
`cron.schedule(...)` locally. Then deploy with `ENABLE_PG_CRON=1` set for the
app container that runs migrations.

### Google Cloud SQL

Do not use the Docker image; enable pg_cron with the instance flag instead:

1. Set the flag `cloudsql.enable_pg_cron=on` and
   `cron.database_name=<application database>`, then restart the instance.
2. Deploy the app with `ENABLE_PG_CRON=1` so the migration registers the job.

## Verifying

```sql
-- the registered job
SELECT jobid, jobname, schedule, command, active FROM cron.job
 WHERE jobname = 'refresh-pygeoapi-materialized-views';

-- recent run history
SELECT status, start_time, end_time, return_message
  FROM cron.job_run_details
 WHERE jobid = (SELECT jobid FROM cron.job
                 WHERE jobname = 'refresh-pygeoapi-materialized-views')
 ORDER BY start_time DESC LIMIT 5;
```

## Manual / ad-hoc refresh

Independent of the cron job, the views can be refreshed on demand with the CLI
(also useful in development, where the cron job does not exist):

```bash
oco refresh-pygeoapi-materialized-views                 # all views, plain
oco refresh-pygeoapi-materialized-views --concurrently  # no read lock
```

### Note on non-concurrent REFRESH

The cron helper uses plain `REFRESH MATERIALIZED VIEW`, not `CONCURRENTLY`,
because `REFRESH ... CONCURRENTLY` cannot run inside the implicit transaction of
a PL/pgSQL function. Plain refresh takes a brief exclusive lock on each view,
which is acceptable in the off-peak nightly window. The CLI still offers
`--concurrently` for daytime manual refreshes (every view has the required
unique index).
