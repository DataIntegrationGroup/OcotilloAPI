# ===============================================================================
# Copyright 2026 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
"""DEPRECATED: standalone orchestrator for the NM_Wells (geothermal) migration.

Deprecated alongside ``transfers/transfer.py`` (the NM_Aquifer driver): both
legacy migration drivers are frozen. Do not add new migrations here. The
``NMW_*`` staging tables this loads remain in service -- live API routes still
read them -- so the loader is kept runnable for backfills and re-runs, but it
gets no new features and its tests no longer gate CI.

This script runs the NM_Wells Phase-1 staging migration:

1. Reference -> lexicon load (``ref_*`` lookups), gated by
   ``TRANSFER_GEOTHERMAL_REFERENCE`` (default True).
2. NM_Wells 1:1 staging mirror load into the ``NMW_*`` tables, gated by
   ``TRANSFER_NMW_MIRROR`` (default True). Row source is a SQL Server data dump
   when ``NMW_SQL_DUMP`` is set, otherwise per-table CSV exports.

Assumes the schema already exists (run ``alembic upgrade head`` first). Does not
drop/rebuild the database.

Run:
    python -m transfers.transfer_geothermal
Env:
    TRANSFER_LIMIT=1000                # rows per table (0/unset = all)
    NMW_SQL_DUMP=/path/to/data.sql     # optional; else CSV
    TRANSFER_GEOTHERMAL_REFERENCE=1
    TRANSFER_NMW_MIRROR=1
"""

import os
import warnings

from dotenv import load_dotenv

# Load .env FIRST, before any database imports. Do not override env vars already
# set by the runtime (e.g. Cloud Run jobs).
load_dotenv(override=False)

# In managed runtimes DB_DRIVER is sometimes omitted while CLOUD_SQL_* are set.
if (
    not (os.getenv("DB_DRIVER") or "").strip()
    and (os.getenv("CLOUD_SQL_INSTANCE_NAME") or "").strip()
):
    os.environ["DB_DRIVER"] = "cloudsql"

from db.engine import session_ctx  # noqa: E402
from services.env import get_bool_env  # noqa: E402
from transfers.logger import logger  # noqa: E402
from transfers.nmw_mirror_transfer import (  # noqa: E402
    refresh_materialized_views,
    transfer_nmw_mirror,
)
from transfers.reference_lexicon_transfer import transfer_reference_tables  # noqa: E402


def run_geothermal_transfer(limit: int = None) -> dict:
    """Run the NM_Wells geothermal staging migration. Returns a summary dict."""
    warnings.warn(
        "transfers.transfer_geothermal is deprecated; the NM_Wells migration "
        "drivers are frozen and receive no new migrations.",
        DeprecationWarning,
        stacklevel=2,
    )
    limit = int(limit if limit is not None else os.getenv("TRANSFER_LIMIT", 0) or 0)
    summary: dict = {}

    logger.info("========== NM_WELLS (GEOTHERMAL) MIGRATION ==========")
    logger.info("limit=%s", limit or "all")

    if get_bool_env("TRANSFER_GEOTHERMAL_REFERENCE", True):
        logger.info("---- Reference tables -> lexicon ----")
        with session_ctx() as session:
            tables, created, errors = transfer_reference_tables(session, limit=limit)
        summary["reference"] = {
            "tables": tables,
            "terms_created": created,
            "errors": len(errors),
        }
    else:
        logger.info("Skipping reference->lexicon (TRANSFER_GEOTHERMAL_REFERENCE=0)")

    if get_bool_env("TRANSFER_NMW_MIRROR", True):
        logger.info("---- NM_Wells 1:1 staging mirror ----")
        with session_ctx() as session:
            tables, inserted, errors = transfer_nmw_mirror(session, limit=limit)
        summary["mirror"] = {
            "tables": tables,
            "rows_inserted": inserted,
            "errors": len(errors),
        }
        logger.info("---- Refresh materialized OGC views ----")
        with session_ctx() as session:
            summary["refreshed_views"] = refresh_materialized_views(session)
    else:
        logger.info("Skipping NM_Wells mirror (TRANSFER_NMW_MIRROR=0)")

    logger.info("NM_Wells migration complete: %s", summary)
    return summary


def main() -> None:
    run_geothermal_transfer()


if __name__ == "__main__":
    main()


# ============= EOF =============================================
