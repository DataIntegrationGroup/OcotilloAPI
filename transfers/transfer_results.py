from __future__ import annotations

import argparse
from pathlib import Path

from transfers.transfer_results_builder import TransferResultsBuilder
from transfers.transfer_results_specs import (
    TRANSFER_COMPARISON_SPECS,
    TransferComparisonSpec,
)
from transfers.transfer_results_types import *  # noqa: F401,F403

__all__ = [
    "TransferResultsBuilder",
    "TransferComparisonSpec",
    "TRANSFER_COMPARISON_SPECS",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare each transfer input CSV against destination Postgres rows."
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("transfers") / "metrics" / "transfer_results_summary.md",
        help="Output path for markdown summary table.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=25,
        help="Max missing/extra key samples stored per transfer.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    builder = TransferResultsBuilder(sample_limit=args.sample_limit)
    results = builder.build()
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    TransferResultsBuilder.write_summary(args.summary_path, results)
    print(f"Wrote comparison summary: {args.summary_path}")
    print(f"Transfer comparisons: {len(results.results)}")


if __name__ == "__main__":
    main()
