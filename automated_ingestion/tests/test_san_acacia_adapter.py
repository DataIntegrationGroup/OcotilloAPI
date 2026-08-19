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
Adapter behaviour: what it refuses, and that one bad row costs only that row.
"""

from automated_ingestion.sources.san_acacia.adapter import SanAcaciaAdapter


def _row(**overrides):
    row = {
        "monitoring_point_id": 40,
        "dateAndTime": "2024-10-30T20:00:00",
        "level": 471.518,
        "unit": "cm",
        "reference": 3,
    }
    row.update(overrides)
    return row


def test_maps_a_good_row():
    [observation] = list(SanAcaciaAdapter().to_observations([_row()]))
    assert observation.external_point_id == "sanacaciareach-40"
    assert observation.value == 15.469751
    assert observation.units == "ft"


def test_wrong_datum_is_refused():
    # The datum is chosen at request time and cannot be recovered from the row,
    # so a reading fetched against another reference has unknown meaning.
    adapter = SanAcaciaAdapter()
    assert list(adapter.to_observations([_row(reference=1)])) == []
    assert "not 3" in adapter.failures[0]["error"]


def test_unexpected_unit_is_refused():
    # Converting a value whose unit is not what it claims is wrong by a factor
    # of 30.48 and still looks like a plausible depth.
    adapter = SanAcaciaAdapter()
    assert list(adapter.to_observations([_row(unit="ft")])) == []
    assert "expected 'cm'" in adapter.failures[0]["error"]


def test_one_bad_row_does_not_lose_the_others():
    adapter = SanAcaciaAdapter()
    rows = [_row(), _row(dateAndTime="broken"), _row(dateAndTime="2024-10-30T21:00:00")]
    assert len(list(adapter.to_observations(rows))) == 2
    assert len(adapter.failures) == 1


def test_failures_identify_the_record():
    adapter = SanAcaciaAdapter()
    list(adapter.to_observations([_row(level=None)]))
    assert adapter.failures[0]["record"] == "40@2024-10-30T20:00:00"


# ============= EOF =============================================
