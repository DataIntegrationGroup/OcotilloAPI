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

from db import ThingContactAssociation, Thing, Contact, Location
from db.engine import session_ctx
from transfers.contact_transfer import ContactTransfer
from transfers.well_transfer import WellTransferer


def test_multiple_wells():
    pointids = ["MG-022", "MG-030", "MG-043"]
    wt = WellTransferer(pointids=pointids)
    wt.transfer()

    ct = ContactTransfer(pointids=pointids)
    ct.transfer()

    with session_ctx() as sess:
        assert sess.query(ThingContactAssociation).count() == 6

        # cleanup
        sess.query(Contact).delete()
        sess.query(ThingContactAssociation).delete()
        sess.query(Location).delete()
        sess.query(Thing).delete()
        sess.commit()


# ============= EOF =============================================
