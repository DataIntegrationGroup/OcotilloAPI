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

from fastapi import FastAPI

from core.dependencies import session_dependency
from transfers.asset_transfer import transfer_assets_testing
from transfers.contact_transfer import transfer_contacts
from transfers.group_transfer import transfer_groups
from transfers.link_ids_transfer import transfer_link_ids, transfer_link_ids_welldata
from transfers.thing_transfer import (
    transfer_met,
    transfer_ephemeral_stream,
    transfer_perennial_stream,
    transfer_springs,
)
from transfers.transfer import message, main_transfer, transfer_all
from transfers.waterlevels_transfer import transfer_water_levels
from transfers.well_transfer import transfer_wells, cleanup_wells

app = FastAPI(title="Transfer Service")


@app.post("/wells")
async def wells(
    session: session_dependency,
    start_index: int,
    limit: int = 25,
):
    results = transfer_wells(session, start_index=start_index, limit=limit)
    return results


@app.post("/spring")
async def _(session: session_dependency, limit: int = 25):
    message("TRANSFERRING SPRINGS")
    transfer_springs(session, limit)


@app.post("/perennial_stream")
async def _(session: session_dependency, limit: int = 25):
    message("TRANSFERRING PERENNIAL STREAMS")
    transfer_perennial_stream(session, limit)


@app.post("/ephemeral_stream")
async def _(session: session_dependency, limit: int = 25):
    message("TRANSFERRING EPHEMERAL STREAMS")
    transfer_ephemeral_stream(session, limit)


@app.post("/met")
async def _(session: session_dependency, limit: int = 25):
    message("TRANSFERRING METEOROLOGICAL")
    transfer_met(session, limit)


@app.post("/contacts")
async def _(session: session_dependency):
    message("TRANSFERRING CONTACTS")
    transfer_contacts(session)


@app.post("/waterlevels")
async def _(session: session_dependency):
    message("TRANSFERRING WATER LEVELS")
    transfer_water_levels(session)


@app.post("/link_ids")
async def _(session: session_dependency):
    message("TRANSFERRING LINK IDS")
    transfer_link_ids(session)
    transfer_link_ids_welldata(session)


@app.post("assets")
async def _transfer_assets(session: session_dependency):
    message("TRANSFERRING ASSETS")
    transfer_assets_testing(session)


@app.post("/groups")
async def _transfer_groups(session: session_dependency):
    message("TRANSFERRING GROUPS")
    transfer_groups(session)


@app.post("/cleanup_wells")
async def _cleanup_wells(session: session_dependency):
    cleanup_wells(session)


@app.post("/main_transfer")
async def _(session: session_dependency):
    message("TRANSFERRING ALL")
    transfer_all(session)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============= EOF =============================================
