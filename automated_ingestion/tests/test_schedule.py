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
The weekly schedule selects what it claims to.

A group name is a string, so a typo yields a schedule that runs successfully and
ingests nothing -- which looks like everything is fine.
"""

from dagster import DefaultScheduleStatus

from automated_ingestion.defs.definitions import defs

EXPECTED = {
    "raw_san_acacia_locations",
    "raw_san_acacia_readings",
    "san_acacia_observations",
}


def _schedule():
    return next(s for s in defs.schedules if s.name == "san_acacia_weekly")


def test_the_schedule_is_registered():
    assert _schedule().job.name == "san_acacia_ingest"


def test_it_selects_every_san_acacia_asset_and_nothing_else():
    selected = {
        key.to_user_string()
        for key in _schedule().job.selection.resolve(list(defs.assets))
    }
    assert selected == EXPECTED


def test_operations_assets_are_excluded():
    # ingestion_heartbeat and database_connectivity are diagnostics. Running
    # them weekly would add noise and, for connectivity, a pointless query.
    selected = {
        key.to_user_string()
        for key in _schedule().job.selection.resolve(list(defs.assets))
    }
    assert "ingestion_heartbeat" not in selected
    assert "database_connectivity" not in selected


def test_it_runs_weekly_in_local_time():
    schedule = _schedule()
    assert schedule.cron_schedule == "0 5 * * 1"
    assert schedule.execution_timezone == "America/Denver"


def test_it_is_stopped_until_somebody_starts_it():
    # Turning it on begins writing to Ocotillo, and the first run for the wells
    # without history fetches back to the floor. That is a decision, not a
    # consequence of a merge.
    assert _schedule().default_status is DefaultScheduleStatus.STOPPED


# ============= EOF =============================================
