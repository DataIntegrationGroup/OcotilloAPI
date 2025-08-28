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
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .initializers import init_db, init_lexicon
from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler to initialize the database and lexicon.
    """
    if settings.get_enum("MODE") == "development":
        init_db()
        init_lexicon()
    yield


app = FastAPI(
    title="Sample Location API",
    description="API for managing sample locations",
    version="0.0.1",
    lifespan=lifespan,
)

# ============= EOF =============================================
