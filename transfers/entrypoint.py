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
from transfers.well_transfer import transfer_wells

app = FastAPI(title="Transfer Service")


@app.post("/wells")
async def wells(session: session_dependency,
                start_index: int,
                limit: int=25, ):

    results = transfer_wells(session, start_index=start_index, limit=limit)
    return results


@app.get("/health")
async def health():
    return {"status": "ok"}


# ============= EOF =============================================
