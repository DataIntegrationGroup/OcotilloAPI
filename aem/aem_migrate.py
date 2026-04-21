# flake8: noqa: E501
from __future__ import annotations

import argparse
import logging
import sys

from services.aem_migration import MigrationRunner

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Deprecated wrapper around oco aem-ingest batch migration"
    )
    parser.add_argument("--mapping", required=True, help="Path to gcs_path_mapping.csv")
    parser.add_argument(
        "--bucket",
        required=True,
        help="GCS bucket name (e.g. nmbgmr-aem-data)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Local root path override for personal Drive copies",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log all actions without uploading anything",
    )
    parser.add_argument(
        "--survey",
        default=None,
        help="Only migrate this survey_id (e.g. estancia_2025)",
    )
    parser.add_argument(
        "--stage",
        default=None,
        help="Only migrate this processing_stage",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel upload threads (default: 4)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only migrate the first N filtered rows",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )

    logger.warning(
        "aem/aem_migrate.py is deprecated. Use `python -m cli.cli aem-ingest batch` instead."
    )

    runner = MigrationRunner(
        mapping_path=args.mapping,
        bucket_name=args.bucket,
        root_override=args.root,
    )
    runner.run(
        dry_run=args.dry_run,
        survey_filter=args.survey,
        stage_filter=args.stage,
        workers=args.workers,
        limit=args.limit,
    )
    runner.write_outputs()

    if runner.failed_rows:
        logger.error(
            "%d files failed — see migration_failures.csv", len(runner.failed_rows)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
