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
Plain structures passed from an adapter to the loader.

These are deliberately not SQLAlchemy models. An adapter is pure and testable
without a database session; turning these into rows is the loader's job.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ObservationRecord:
    """One timestamped reading, already in Ocotillo's units and datum."""

    external_point_id: str
    """The vendor's identifier for the monitoring point."""

    observation_datetime: datetime
    """Timezone-aware instant of the reading."""

    value: float
    """Measurement in ``units``, on the datum the source's mapping fixes."""

    units: str
    """Unit symbol as it appears in the Ocotillo lexicon."""


# ============= EOF =============================================
