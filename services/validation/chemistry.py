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
from schemas.create.chemistry import CreateWaterChemistryAnalysis
from services.validation import get_category


async def validate_analyte(analysis_data: CreateWaterChemistryAnalysis):
    session = database_sessionmaker()
    with session:
        # get valid analytes from the database
        valid_analytes = await get_category("water_chemistry")

        if analysis_data.analyte not in valid_analytes:
            raise ValueError(
                f"Invalid analyte: {analysis_data.analyte}. "
                f"Valid options are: {', '.join(valid_analytes)}."
            )
    return analysis_data


# ============= EOF =============================================
