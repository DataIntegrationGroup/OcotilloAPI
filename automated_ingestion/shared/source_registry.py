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
Registry of ingestion sources.

Each source declares itself once here so jobs, schedules, and the backfill
factory can enumerate sources without importing each one by name.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    """Static description of one ingestion source."""

    key: str
    """Stable identifier, used in asset keys and GCS prefixes."""

    display_name: str
    """Human-readable name for logs and the Dagster UI."""

    dataset_name: str
    """dlt dataset name; becomes the top-level GCS prefix."""


_SOURCES: dict[str, SourceDefinition] = {}


def register(source: SourceDefinition) -> SourceDefinition:
    """Add a source to the registry, rejecting duplicate keys."""
    if source.key in _SOURCES:
        raise ValueError(f"Source {source.key!r} is already registered.")
    _SOURCES[source.key] = source
    return source


def get_source(key: str) -> SourceDefinition:
    """Look up a registered source by key."""
    try:
        return _SOURCES[key]
    except KeyError:
        raise KeyError(f"No ingestion source registered under {key!r}.") from None


def all_sources() -> tuple[SourceDefinition, ...]:
    """Every registered source, ordered by key."""
    return tuple(_SOURCES[k] for k in sorted(_SOURCES))


# ============= EOF =============================================
