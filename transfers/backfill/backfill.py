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
"""
Orchestrates the backfill pipeline used in CD workflows.

Preferred usage (avoids import path issues):
    python -m transfers.backfill.backfill --batch-size 1000
"""

import argparse
import sys
from pathlib import Path

# Ensure repository root on sys.path when run as a script (e.g., in CI).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.util import get_bool_env
from transfers.logger import logger


def run(batch_size: int = 1000) -> None:
    """
    Execute all backfill steps in a deterministic order.

    Currently, no concrete backfill steps are registered. This function is kept
    as a stable orchestration entry point (used by CD/CLI) and will be wired
    up to real backfill steps in future refactoring work.
    """
    # NOTE: Intentionally empty; this serves as a placeholder until concrete
    # backfill steps are implemented and registered in this tuple.
    steps = ()
    for name, fn, flag in steps:
        if not get_bool_env(flag, True):
            logger.info(f"Skipping backfill: {name} ({flag}=false)")
            continue
        logger.info(f"Starting backfill: {name}")
        result = fn(batch_size)
        logger.info(
            f"Completed backfill: {name} — "
            f"inserted={result.inserted} updated={result.updated} "
            f"skipped_orphans={result.skipped_orphans} errors={len(result.errors)}"
        )
        if result.errors:
            for err in result.errors:
                logger.warning(f"  {name}: {err}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run backfill pipeline.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows to insert per batch.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(batch_size=args.batch_size)
    except Exception as exc:
        logger.critical("Backfill orchestration failed", exc_info=True)
        sys.exit(1)

# ============= EOF =============================================
