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
A named job wrapping the heartbeat asset, so a deploy can be smoke-tested
without the Dagster+ UI.

The asset alone is not enough for that: `dagster-cloud-action`'s `launch_job`
identifies what to run by job name and exposes no asset selection, so an asset
reachable only through the implicit `__ASSET_JOB` cannot be launched from CI.
`.github/workflows/smoke_dagster_location.yml` runs this one.

Worth having because a successful deploy is weaker evidence than a successful
run. The agent loading the code location proves the *loader* process can import
the package; it says nothing about the process that executes a step, which is a
different process with a different sys.path. See the note in
`assets/heartbeat.py` -- that gap is the whole reason the asset exists, and this
job is how CI closes it.
"""

from dagster import AssetSelection, define_asset_job

from automated_ingestion.defs.assets.heartbeat import ingestion_heartbeat

heartbeat_job = define_asset_job(
    name="ingestion_heartbeat_check",
    selection=AssetSelection.assets(ingestion_heartbeat),
    description=(
        "Materialize the heartbeat asset only. Touches no database, no network, "
        "and no GCS, so a failure is a packaging or deployment problem."
    ),
    # No retry policy. A retry would mask exactly the failure this job exists to
    # surface: an import that works at load time and fails at execution does so
    # deterministically.
)

# ============= EOF =============================================
