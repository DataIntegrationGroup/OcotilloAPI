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

from pathlib import Path

from db import ThingContactAssociation
from db.engine import session_ctx
from transfers.contact_transfer import ContactTransfer
from transfers.well_transfer import WellTransferer


def test_multiple_wells():
    base_dir = Path(__file__).resolve().parents[2]
    csv_dir = base_dir / "transfers" / "data"
    csv_paths = {
        "WellData": csv_dir / "WellData.csv",
        "Location": csv_dir / "Location.csv",
        "OwnersData": csv_dir / "OwnersData.csv",
        "OwnerLink": csv_dir / "OwnerLink.csv",
    }
    pointids = ["TV-230", "EB-317", "SA-0313"]
    wt = WellTransferer(pointids=pointids, flags={"CSV_PATHS": csv_paths})
    wt.transfer()

    ct = ContactTransfer(pointids=pointids, flags={"CSV_PATHS": csv_paths})
    ct.transfer()

    with session_ctx() as sess:
        assert sess.query(ThingContactAssociation).count() == 6


# ============= EOF =============================================
