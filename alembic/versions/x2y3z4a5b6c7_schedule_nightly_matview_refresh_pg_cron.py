"""schedule nightly materialized-view refresh via pg_cron

Registers a pg_cron job that refreshes the materialized views once a
night. The job calls a SQL helper function,
``public.refresh_materialized_views()``, which discovers every
materialized view in the public schema from the catalog at run time -- so
this migration stays immutable and self-contained, and views added by
later migrations are refreshed without any rescheduling.

This also drops the legacy ``refresh_pygeoapi_materialized_views`` helper
(created by ``d5e6f7a8b9c0``) on databases that already ran that revision,
folding it into the generically named function.

pg_cron is a *production-only* dependency. It requires the extension to be
loaded via ``shared_preload_libraries`` on the database server, which the
development docker-compose Postgres image does not do. To avoid breaking
``alembic upgrade head`` in development (and in test/CI), this migration is a
no-op unless ``ENABLE_PG_CRON`` is truthy in the environment. Production sets
``ENABLE_PG_CRON=1``; everywhere else the migration records itself as applied
without touching pg_cron. See ``docs/pg_cron-nightly-refresh.md``.

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2026-06-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

from services.env import get_bool_env

# revision identifiers, used by Alembic.
revision: str = "x2y3z4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "w1x2y3z4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Name of the pg_cron job. Used to (re)register and to unschedule.
CRON_JOB_NAME = "refresh-materialized-views"

# Legacy helper created by d5e6f7a8b9c0, superseded by refresh_materialized_views.
LEGACY_FUNCTION_NAME = "refresh_pygeoapi_materialized_views"

# Nightly schedule in standard cron syntax. pg_cron interprets this in the
# database server's timezone (UTC on Cloud SQL / the docker image), so 09:00
# UTC is roughly 02:00-03:00 in US Mountain time -- comfortably off-peak.
CRON_SCHEDULE = "0 9 * * *"


# Helper function the cron job calls. It discovers every materialized view in
# the public schema from the catalog at run time rather than from a baked-in
# list. This keeps the migration immutable and self-contained -- it does not
# depend on mutable application code, and views added by later migrations are
# picked up automatically without rescheduling.
#
# Plain (non-concurrent) REFRESH is used deliberately: REFRESH ... CONCURRENTLY
# cannot run inside the implicit transaction of a PL/pgSQL function, and the
# nightly window tolerates the brief exclusive lock.
_REFRESH_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public.refresh_materialized_views()
RETURNS void
LANGUAGE plpgsql
AS $func$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT matviewname
        FROM pg_matviews
        WHERE schemaname = 'public'
        ORDER BY matviewname
    LOOP
        EXECUTE format('REFRESH MATERIALIZED VIEW %I', r.matviewname);
    END LOOP;
END;
$func$;
"""


def _pg_cron_enabled() -> bool:
    """pg_cron is only wired up where the server explicitly enables it."""
    return get_bool_env("ENABLE_PG_CRON", False) is True


def upgrade() -> None:
    if not _pg_cron_enabled():
        print(
            "ENABLE_PG_CRON is not set; skipping pg_cron job registration "
            "(expected in development, test, and CI)."
        )
        return

    bind = op.get_bind()

    # Requires shared_preload_libraries to include 'pg_cron' and the extension
    # to be creatable in this database (cron.database_name = this DB). See docs.
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron"))

    # (Re)create the refresh helper.
    op.execute(text(_REFRESH_FUNCTION_SQL))

    # Remove the legacy helper on databases that already ran d5e6f7a8b9c0.
    op.execute(text(f"DROP FUNCTION IF EXISTS public.{LEGACY_FUNCTION_NAME}()"))

    # Drop any previously registered job with the same name so re-running this
    # migration (or a re-deploy) does not accumulate duplicate schedules.
    op.execute(
        text(
            "SELECT cron.unschedule(jobid) FROM cron.job " "WHERE jobname = :name"
        ).bindparams(name=CRON_JOB_NAME)
    )

    bind.execute(
        text("SELECT cron.schedule(:name, :sched, :cmd)").bindparams(
            name=CRON_JOB_NAME,
            sched=CRON_SCHEDULE,
            cmd="SELECT public.refresh_materialized_views();",
        )
    )

    print(
        f"Registered pg_cron job '{CRON_JOB_NAME}' "
        f"(schedule '{CRON_SCHEDULE}', server timezone)."
    )


def downgrade() -> None:
    if not _pg_cron_enabled():
        print("ENABLE_PG_CRON is not set; nothing to unschedule.")
        return

    op.execute(
        text(
            "SELECT cron.unschedule(jobid) FROM cron.job " "WHERE jobname = :name"
        ).bindparams(name=CRON_JOB_NAME)
    )
    op.execute(
        text("DROP FUNCTION IF EXISTS public.refresh_materialized_views()")
    )
    # The pg_cron extension itself is left installed: it is a server-level
    # capability that other jobs may depend on, and dropping it is not the
    # inverse of "schedule a job".
