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
Choosing the deployment a water level belongs to.

A well carries several open deployments because a deployment is equipment, not a
measured property. Picking the wrong one attributes a water level to a cable.
"""

from datetime import date

from automated_ingestion.sources.san_acacia.resolve import (
    DeploymentCandidate,
    ResolutionKind,
    resolve_deployment,
)

# The real equipment on SO-0140 in staging.
DIVERLINK = DeploymentCandidate(436, "DiverLink")
TRANSDUCER = DeploymentCandidate(437, "Pressure Transducer")
CABLE = DeploymentCandidate(438, "Diver Cable")


def test_the_transducer_is_chosen_from_a_full_nest():
    resolution = resolve_deployment([DIVERLINK, TRANSDUCER, CABLE])
    assert resolution.kind is ResolutionKind.RESOLVED
    assert resolution.deployment_id == 437


def test_a_barometer_is_not_a_water_level():
    # Barometers are deployed on these wells too, and measure air pressure.
    resolution = resolve_deployment([DeploymentCandidate(500, "Barometer"), TRANSDUCER])
    assert resolution.deployment_id == 437


def test_two_open_transducers_are_ambiguous():
    # Two of the 38 wells are in this state. Taking the lower id would be a
    # guess about equipment, made silently.
    resolution = resolve_deployment(
        [TRANSDUCER, DeploymentCandidate(600, "Pressure Transducer")]
    )
    assert resolution.kind is ResolutionKind.AMBIGUOUS
    assert resolution.deployment_id is None
    assert resolution.candidates == (437, 600)
    assert resolution.needs_a_human


def test_no_transducer_is_missing_not_invented():
    # SO-0246 has no open transducer deployment at all.
    resolution = resolve_deployment([DIVERLINK, CABLE])
    assert resolution.kind is ResolutionKind.MISSING
    assert resolution.deployment_id is None


def test_a_removed_transducer_is_not_a_fallback():
    # Writing today's readings against retired equipment would be worse than
    # skipping the well, because it would look like it worked.
    resolution = resolve_deployment(
        [DeploymentCandidate(700, "Pressure Transducer", removal_date=date(2024, 1, 1))]
    )
    assert resolution.kind is ResolutionKind.MISSING


def test_a_removed_transducer_does_not_make_a_live_one_ambiguous():
    resolution = resolve_deployment(
        [
            DeploymentCandidate(
                700, "Pressure Transducer", removal_date=date(2024, 1, 1)
            ),
            TRANSDUCER,
        ]
    )
    assert resolution.deployment_id == 437


def test_no_deployments_at_all():
    assert resolve_deployment([]).kind is ResolutionKind.MISSING


# ============= EOF =============================================
