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
The nightly groundwater level export (OCO-79).

Selected by group, like San Acacia, so the five steps run in dependency order
and a step added to the group joins the job without this file changing.
"""

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    RetryPolicy,
    ScheduleDefinition,
    define_asset_job,
)

from automated_ingestion.defs.assets.groundwater_level_export import GROUP

groundwater_level_export_job = define_asset_job(
    name="groundwater_level_export",
    selection=AssetSelection.groups(GROUP),
    description=(
        "Snapshot public groundwater levels, write a GeoParquet and CSV per "
        "changed well, check them, publish to GCS, and register STAC items."
    ),
    # One retry: every step is repeatable (the state commit is last), so a
    # retry is safe, and a transient Cloud Run or STAC API failure is the
    # likely cause. A second failure is a real problem.
    op_retry_policy=RetryPolicy(max_retries=1, delay=120),
    # Two runs must not interleave steps on one bucket. Dagster+ enforces
    # this through a deployment-level run queue limit on this tag
    # (tag_concurrency_limits: key ocotillo/export, value gwl, limit 1) --
    # see docs/groundwater-level-export.md.
    tags={"ocotillo/export": "gwl"},
)

groundwater_level_export_nightly = ScheduleDefinition(
    name="groundwater_level_export_nightly",
    job=groundwater_level_export_job,
    # 02:15 America/Denver: after the day's field data is entered, before
    # anyone downloads in the morning. Nightly is OCO-79's working assumption,
    # not a confirmed requirement.
    cron_schedule="15 2 * * *",
    execution_timezone="America/Denver",
    # Stopped by default: turning it on starts publishing to a public bucket
    # and a STAC API. That is a decision, taken once, not a side effect of a
    # merge -- and the public-well definition (SBAC) must be settled first.
    default_status=DefaultScheduleStatus.STOPPED,
    description="Nightly groundwater level export. Unchanged wells are skipped.",
)


# ============= EOF =============================================
