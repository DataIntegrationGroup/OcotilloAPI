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
from db import LocationThingAssociation, Thing, WellThing


def add_well(session, data):
    location_id = data.pop("location_id", None)
    assoc = LocationThingAssociation()

    thing = Thing()
    session.add(thing)
    session.commit()
    session.refresh(thing)

    well = WellThing(**data)
    well.thing_id = thing.id
    session.add(well)
    session.commit()
    session.refresh(well)

    assoc.location_id = location_id
    assoc.thing_id = thing.id
    session.add(assoc)
    session.commit()
    return well
# ============= EOF =============================================
