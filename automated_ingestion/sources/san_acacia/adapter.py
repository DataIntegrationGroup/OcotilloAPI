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
Van Essen mapping rules for the San Acacia source.

The adapter is the only place the vendor's vocabulary meets Ocotillo's. It is
pure enough to test without a database: it takes raw records and returns
structures, and the loader turns those into rows.

Per-record failure isolation matches the rest of the pipeline. One unparseable
reading costs that reading, not the series -- a diver that logs one bad row
should not lose a month of good ones.
"""

from collections.abc import Iterable, Iterator
from typing import Any

from domain.van_essen import (
    GROUND_SURFACE_REFERENCE,
    MEASUREMENT_UNIT,
    VanEssenMappingError,
    depth_to_water_ft,
    external_point_key,
    parse_reading_timestamp,
)

from automated_ingestion.ocotillo.adapter import SourceAdapter
from automated_ingestion.ocotillo.structs import ObservationRecord


class SanAcaciaAdapter(SourceAdapter):
    """Maps Diver-HUB water levels onto Ocotillo observations."""

    def __init__(self) -> None:
        self.failures: list[dict[str, Any]] = []

    @property
    def source_key(self) -> str:
        return "san_acacia"

    def to_observations(
        self, records: Iterable[dict[str, Any]]
    ) -> Iterator[ObservationRecord]:
        """Convert raw rows, collecting per-record failures rather than raising.

        Rows whose ``reference`` is not ground surface are refused outright. The
        datum is chosen at request time and cannot be recovered from the row, so
        accepting one would mean storing a number whose meaning is unknown --
        the single failure this pipeline must not produce quietly.
        """
        for record in records:
            try:
                yield self._to_observation(record)
            except VanEssenMappingError as exc:
                self.failures.append({"record": _identify(record), "error": str(exc)})

    def _to_observation(self, record: dict[str, Any]) -> ObservationRecord:
        reference = record.get("reference")
        if reference != GROUND_SURFACE_REFERENCE:
            raise VanEssenMappingError(
                f"Reading was fetched with reference={reference!r}, not "
                f"{GROUND_SURFACE_REFERENCE} (ground surface). Its datum is not "
                "recoverable from the row."
            )

        unit = record.get("unit")
        if unit != "cm":
            raise VanEssenMappingError(
                f"Reading unit is {unit!r}, expected 'cm'. Converting a value "
                "whose unit is not what it claims would be wrong by a factor."
            )

        point_id = record.get("monitoring_point_id")
        value = depth_to_water_ft(record.get("level"))
        if value is None:
            raise VanEssenMappingError("Reading has no level; nothing to store.")

        return ObservationRecord(
            external_point_id=external_point_key(point_id),
            observation_datetime=parse_reading_timestamp(record.get("dateAndTime")),
            value=value,
            units=MEASUREMENT_UNIT,
        )


def _identify(record: dict[str, Any]) -> str:
    """A short handle for a failed record, for logs and metadata."""
    return f"{record.get('monitoring_point_id')}@{record.get('dateAndTime')}"


# ============= EOF =============================================
