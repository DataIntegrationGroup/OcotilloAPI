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
Base class for source adapters.

An adapter converts one source's raw records into Ocotillo structures. It is
the only place a vendor's vocabulary appears alongside Ocotillo's, which keeps
vendor quirks out of ``domain/`` and out of the loader.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import Any

from automated_ingestion.ocotillo.structs import ObservationRecord


class SourceAdapter(ABC):
    """Maps one source's raw records onto Ocotillo structures."""

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Registry key of the source this adapter serves."""

    @abstractmethod
    def to_observations(
        self, records: Iterable[dict[str, Any]]
    ) -> Iterator[ObservationRecord]:
        """Convert raw vendor records into observation records."""


# ============= EOF =============================================
