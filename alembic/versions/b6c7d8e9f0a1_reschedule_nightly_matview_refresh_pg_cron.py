"""re-register the nightly pg_cron materialized-view refresh

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-07-20

``x2y3z4a5b6c7`` registers the nightly refresh job, but is a no-op unless
``ENABLE_PG_CRON`` is truthy. That variable was set on the ``staging`` copy of
``CD_production.yml`` and never reached the ``production`` / ``hotfix/v*``
line, so when ``x2y3z4a5b6c7`` shipped in ``v1.1.2`` the production migration
step ran it with the flag unset: it returned early and Alembic stamped the
revision as applied. ``refresh_materialized_views()`` and the cron job were
never created, and because the revision is stamped, setting the variable does
not cause it to re-run.

This revision re-runs the registration under a fresh revision id so the
already-stamped one is not in the way. It is deliberately a near-duplicate of
``x2y3z4a5b6c7`` rather than an import of it -- migrations stay self-contained
and immutable.

Still gated on ``ENABLE_PG_CRON`` for the same reason as the original: pg_cron
needs ``shared_preload_libraries``, which the development, test, and CI
Postgres images do not provide. Everything here is idempotent, so it is safe
on a database where the job already exists. See
``docs/pg_cron-nightly-refresh.md``.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

from services.env import get_bool_env

# revision identifiers, used by Alembic.
revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match x2y3z4a5b6c7 -- this re-registers that same job, it does not add
# a second one.
CRON_JOB_NAME = "refresh-materialized-views"
CRON_SCHEDULE = "0 9 * * *"

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

    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron"))
    op.execute(text(_REFRESH_FUNCTION_SQL))

    # Drop any job already carrying this name so re-running does not accumulate
    # duplicate schedules.
    op.execute(
        text(
            "SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = :name"
        ).bindparams(name=CRON_JOB_NAME)
    )

    bind.execute(
        text("SELECT cron.schedule(:name, :sched, :cmd)").bindparams(
            name=CRON_JOB_NAME,
            sched=CRON_SCHEDULE,
            cmd="SELECT public.refresh_materialized_views();",
        )
    )


def downgrade() -> None:
    if not _pg_cron_enabled():
        print("ENABLE_PG_CRON is not set; nothing to unschedule.")
        return

    # Only the schedule is removed. refresh_materialized_views() is left in
    # place -- x2y3z4a5b6c7 also claims ownership of it, and dropping it here
    # would break that revision's view of the world.
    op.execute(
        text(
            "SELECT cron.unschedule(jobid) FROM cron.job WHERE jobname = :name"
        ).bindparams(name=CRON_JOB_NAME)
    )
