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
Orchestrates all backfills used in the staging CD pipeline.

Run with:
    python -m transfers.backfill.staging --batch-size 1000
"""

import argparse
import sys
from transfers.backfill.ngwmn_views import run as run_ngwmn_views
from transfers.backfill.waterlevelscontinuous_pressure_daily import (
    run as run_pressure_daily,
)
from transfers.logger import logger


def run(batch_size: int = 1000) -> None:
    """
    Execute all backfill steps in a deterministic order.
    """
    steps = (
        ("WaterLevelsContinuous_Pressure_Daily", run_pressure_daily),
        ("NGWMN views", lambda: run_ngwmn_views(batch_size=batch_size)),
    )

    for name, fn in steps:
        logger.info(f"Starting backfill: {name}")
        fn(batch_size=batch_size)
        logger.info(f"Completed backfill: {name}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run staging backfills.")
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
        logger.critical(f"Backfill orchestration failed: {exc}")
        sys.exit(1)

# ============= EOF =============================================
