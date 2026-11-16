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
Entry point for the ``ocotillo-automated-ingestion`` Dagster+ code location.

``[tool.dagster] module_name`` in ``pyproject.toml`` points here, so this is
what ``dagster dev`` and the Dagster+ agent import. Keep it thin: it collects
definitions declared elsewhere in the package rather than declaring them here.
"""

from dagster import Definitions, EnvVar

from automated_ingestion.defs.assets import all_assets
from automated_ingestion.defs.jobs.groundwater_level_export import (
    groundwater_level_export_job,
    groundwater_level_export_nightly,
)
from automated_ingestion.defs.jobs.heartbeat import heartbeat_job
from automated_ingestion.defs.jobs.san_acacia import (
    san_acacia_job,
    san_acacia_weekly_schedule,
)
from automated_ingestion.defs.resources import (
    CloudRunJob,
    ExportStorage,
    OcotilloDatabase,
)

defs = Definitions(
    assets=all_assets(),
    jobs=[heartbeat_job, san_acacia_job, groundwater_level_export_job],
    schedules=[san_acacia_weekly_schedule, groundwater_level_export_nightly],
    resources={
        "database": OcotilloDatabase(),
        # EnvVar resolves when a run starts, not when the location loads, so
        # a deployment without the export configured still loads -- only the
        # export's own runs fail, naming the missing variable.
        "cloud_run": CloudRunJob(
            project=EnvVar("GWL_EXPORT_CLOUD_RUN_PROJECT"),
            region=EnvVar("GWL_EXPORT_CLOUD_RUN_REGION"),
            job=EnvVar("GWL_EXPORT_CLOUD_RUN_JOB"),
        ),
        "export_storage": ExportStorage(root=EnvVar("GWL_EXPORT_ROOT")),
    },
)

# ============= EOF =============================================
