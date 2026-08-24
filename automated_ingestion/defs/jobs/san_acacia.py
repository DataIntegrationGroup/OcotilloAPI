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
The scheduled run for San Acacia Reach.

One job over the whole `san_acacia` asset group, so the three steps stay in
order: land the point roster, land the readings, then map and load them. Dagster
resolves that from the asset dependencies rather than from anything declared
here, which is why the selection is by group -- a fourth asset added to the
group joins the schedule without this file changing.

Weekly rather than daily. These are five-minute diver readings and nobody is
watching them in real time; the vendor's endpoint answers 500 when pushed, and a
weekly cadence keeps each run's windows comfortably inside what it serves. The
watermark makes the interval a matter of freshness rather than correctness: a
run fetches from wherever the last one finished, so a missed week is picked up
by the next run rather than lost.
"""

from dagster import (
    AssetSelection,
    DefaultScheduleStatus,
    RetryPolicy,
    ScheduleDefinition,
    define_asset_job,
)

SAN_ACACIA_GROUP = "san_acacia"

san_acacia_job = define_asset_job(
    name="san_acacia_ingest",
    selection=AssetSelection.groups(SAN_ACACIA_GROUP),
    description=(
        "Land the San Acacia point roster and readings in the raw zone, then "
        "map and load them into Ocotillo."
    ),
    # A retry covers the vendor dropping a request or a token expiring mid-run.
    # Two attempts, not more: a persistent 500 means the window is wrong or the
    # endpoint is unwell, and hammering it makes both worse.
    op_retry_policy=RetryPolicy(max_retries=2, delay=60),
)

san_acacia_weekly_schedule = ScheduleDefinition(
    name="san_acacia_weekly",
    job=san_acacia_job,
    # Mondays at 05:00 America/Denver -- after midnight so a run covers whole
    # days, and early enough that a failure is visible at the start of the week
    # rather than discovered the following Monday.
    cron_schedule="0 5 * * 1",
    execution_timezone="America/Denver",
    # Local time rather than UTC deliberately: the wells, the people who read
    # the data, and the working day are all in one timezone, so a schedule that
    # shifts by an hour twice a year would be the surprising choice.
    #
    # Stopped by default. Turning it on starts writing to Ocotillo, and the
    # first run for the 24 wells without history fetches back to the
    # `INITIAL_START` floor. That should be somebody's decision, taken once,
    # rather than a consequence of a merge.
    default_status=DefaultScheduleStatus.STOPPED,
    description=(
        "Weekly San Acacia ingest. Each run resumes from each series' "
        "watermark, so a missed week is caught up rather than lost."
    ),
)


# ============= EOF =============================================
