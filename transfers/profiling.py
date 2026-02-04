"""Utilities for profiling transfer jobs and persisting results.

This module wraps ``cProfile`` execution so that expensive transfers can be
profiled without duplicating boilerplate. Each profiling run generates two
artifacts:

* a ``.prof`` stats file that is compatible with ``snakeviz``/``pstats``
* a human-readable ``.txt`` summary sorted by cumulative time

Artifacts are stored locally under ``transfers/profiles`` (created on demand)
and can optionally be uploaded to the configured GCS bucket.
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Any, Optional

from services.gcs_helper import get_storage_bucket
from transfers.logger import logger


@dataclass
class ProfileArtifact:
    """Paths to the generated profiling artifacts for a transfer run."""

    label: str
    stats_path: Path
    report_path: Path


class TransferProfiler:
    """Profile helper that writes stats + summary files for a callable."""

    def __init__(self, label: str, sort_by: str = "cumulative", report_limit: int = 40):
        safe_label = label.replace(" ", "_").lower()
        timestamp = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

        root = Path("profiles")
        if not os.getcwd().endswith("transfers"):
            root = Path("transfers") / root
        root.mkdir(parents=True, exist_ok=True)

        self.label = safe_label
        self.sort_by = sort_by
        self.report_limit = report_limit
        self.stats_path = root / f"{safe_label}_{timestamp}.prof"
        self.report_path = root / f"{safe_label}_{timestamp}.txt"
        self._profiler = cProfile.Profile()

    def run(
        self, func: Callable[..., Any], *args, **kwargs
    ) -> tuple[Any, ProfileArtifact]:
        """Execute ``func`` under ``cProfile`` and persist artifacts."""

        result = self._profiler.runcall(func, *args, **kwargs)

        # Raw stats for tooling such as snakeviz
        self._profiler.dump_stats(str(self.stats_path))

        # Human-readable summary sorted by cumulative time
        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats(self.sort_by).print_stats(self.report_limit)
        self.report_path.write_text(stream.getvalue())

        artifact = ProfileArtifact(
            label=self.label,
            stats_path=self.stats_path,
            report_path=self.report_path,
        )
        logger.info(
            "Profiled %s: wrote stats to %s and summary to %s",
            self.label,
            self.stats_path,
            self.report_path,
        )
        return result, artifact


def upload_profile_artifacts(artifacts: Optional[Iterable[ProfileArtifact]]) -> None:
    """Upload generated profiling artifacts to the configured storage bucket."""
    if not artifacts:
        logger.info("No profiling artifacts to upload")
        return

    artifacts = list(artifacts)

    bucket = get_storage_bucket()
    for artifact in artifacts:
        for path in (artifact.stats_path, artifact.report_path):
            blob = bucket.blob(f"transfer_profiles/{path.name}")
            blob.upload_from_filename(path)
            logger.info(
                "Uploaded profiling artifact %s to gs://%s/transfer_profiles/%s",
                path,
                bucket.name,
                path.name,
            )


# ============= EOF =============================================
