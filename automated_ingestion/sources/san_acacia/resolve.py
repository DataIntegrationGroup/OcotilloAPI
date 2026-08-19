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
Choosing which deployment a water level belongs to.

A San Acacia well carries several open deployments at once, because a deployment
is a piece of equipment rather than a measured property. SO-0140 has three:

    DiverLink            DN431-1ch    telemetry
    Pressure Transducer  DI801 10m    measures the water level
    Diver Cable          AS2006-6m    the cable

Only the pressure transducer produces the reading being ingested, so that is the
deployment an observation hangs from. Picking any of the others would attribute
a water level to a cable.

Like the reconciler, this never chooses between equally good candidates. Two
open transducers on one well is a question about the equipment record, not
something to resolve by taking the lower id.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import Enum

WATER_LEVEL_SENSOR_TYPE = "Pressure Transducer"
"""The sensor type whose deployment carries a water level.

Checked against staging: of the 38 San Acacia wells, 35 have exactly one open
deployment of this type, 2 have two, and 1 has none. The other types present are
`DiverLink`, `Diver Cable` and `Barometer`, none of which measure depth to
water.
"""

PARAMETER_NAME = "groundwater level"
"""The Ocotillo parameter these readings are. Its `default_unit` is `ft`, which
is what the adapter emits -- the conversion from the vendor's centimetres
happens in `domain/van_essen.py`."""


class ResolutionKind(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    MISSING = "missing"


@dataclass(frozen=True)
class DeploymentCandidate:
    """A deployment on the well, with the bit needed to judge it."""

    deployment_id: int
    sensor_type: str
    removal_date: date | None = None

    @property
    def is_open(self) -> bool:
        return self.removal_date is None


@dataclass(frozen=True)
class Resolution:
    """Which deployment to load into, or why none was chosen."""

    kind: ResolutionKind
    deployment_id: int | None = None
    candidates: tuple[int, ...] = ()

    @property
    def needs_a_human(self) -> bool:
        return self.kind is not ResolutionKind.RESOLVED


def resolve_deployment(candidates: Iterable[DeploymentCandidate]) -> Resolution:
    """Pick the open pressure-transducer deployment, or refuse.

    Closed deployments are excluded rather than preferred-against: a removed
    transducer is not where today's readings belong, and treating it as a
    fallback would quietly write current data against retired equipment.
    """
    open_transducers = [
        c for c in candidates if c.is_open and c.sensor_type == WATER_LEVEL_SENSOR_TYPE
    ]

    if len(open_transducers) == 1:
        return Resolution(
            kind=ResolutionKind.RESOLVED,
            deployment_id=open_transducers[0].deployment_id,
        )
    if len(open_transducers) > 1:
        return Resolution(
            kind=ResolutionKind.AMBIGUOUS,
            candidates=tuple(c.deployment_id for c in open_transducers),
        )
    return Resolution(kind=ResolutionKind.MISSING)


# ============= EOF =============================================
