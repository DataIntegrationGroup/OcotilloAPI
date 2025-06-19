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
from db import database_sessionmaker
from db.lexicon import Lexicon
from schemas.create.well import CreateWellScreen
from services.validation import get_category


async def validate_screens(well_screen_data: CreateWellScreen):
    """
    Validate well screen data before creating a new well screen.
    This function can be extended to include more complex validation logic.
    """
    # Here you can add any additional validation logic if needed
    session = database_sessionmaker()
    with session:
        # get valid screen types from the database
        valid_screen_types = await get_category('casing_material')
        if well_screen_data.screen_type and well_screen_data.screen_type not in valid_screen_types:
            raise ValueError(
                f"Invalid screen_type: {well_screen_data.screen_type}. "
                f"Valid options are: {', '.join(valid_screen_types)}."
            )

    return well_screen_data
# ============= EOF =============================================
