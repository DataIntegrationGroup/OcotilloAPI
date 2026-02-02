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
from transfers.util import read_csv, get_transferable_wells


def main():
    df = read_csv("WellData", dtype={"OSEWelltagID": str})
    df = get_transferable_wells(df)
    df = df[["PointID", "DataSource"]]
    df.to_csv("transferable_wells.csv", index=False, float_format="%.2f")


if __name__ == "__main__":
    main()
# ============= EOF =============================================
