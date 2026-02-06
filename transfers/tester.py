# ===============================================================================
# Copyright 2025 ross
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
from transfers.util import get_transferable_wells, read_csv


def analyze_transferable_wells(csv_name: str = "WellData") -> tuple[int, int]:
    """
    Analyze transferable wells from the given CSV source.

    Parameters
    ----------
    csv_name : str, optional
        The name or path of the CSV data source to read. Defaults to "WellData".

    Returns
    -------
    tuple[int, int]
        A tuple containing:
        - the total number of transferable wells
        - the number of transferable wells with a non-null MPHeight value
    """
    df = read_csv(csv_name)
    wells = get_transferable_wells(df)
    mp = wells[wells["MPHeight"].notna()]
    return len(wells), len(mp)


def main() -> None:
    """
    Entry point for manual execution.

    Reads the default well data source, computes transferable wells and those
    with MPHeight defined, and prints their counts.
    """
    total_wells, mp_wells = analyze_transferable_wells()
    print(total_wells)
    print(mp_wells)


if __name__ == "__main__":
    main()
# ============= EOF =============================================
