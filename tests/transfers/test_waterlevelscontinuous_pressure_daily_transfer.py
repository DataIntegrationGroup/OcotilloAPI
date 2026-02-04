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

import pandas as pd

from transfers.waterlevelscontinuous_pressure_daily import (
    NMA_WaterLevelsContinuous_Pressure_DailyTransferer,
)


def test_pressure_daily_transfer_filters_orphans(water_well_thing):
    transferer = NMA_WaterLevelsContinuous_Pressure_DailyTransferer(batch_size=1)
    df = pd.DataFrame(
        [
            {"PointID": water_well_thing.name, "GlobalID": "gid-1"},
            {"PointID": "MISSING-THING", "GlobalID": "gid-2"},
        ]
    )

    filtered = transferer._filter_to_valid_things(df)

    assert list(filtered["PointID"]) == [water_well_thing.name]


def test_pressure_daily_row_dict_sets_thing_id(water_well_thing):
    transferer = NMA_WaterLevelsContinuous_Pressure_DailyTransferer(batch_size=1)
    row = {"PointID": water_well_thing.name, "GlobalID": "gid-3"}

    mapped = transferer._row_dict(row)

    assert mapped["thing_id"] == water_well_thing.id


# ============= EOF =============================================
