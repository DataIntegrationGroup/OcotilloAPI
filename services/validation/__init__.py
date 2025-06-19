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

async def get_category(category: str) -> list:
    """
    Fetches the categories from the database.

    Returns:
        list: A list of categories.
    """

    session = database_sessionmaker()
    with session:
        categories = [
            lex.term
            for lex in session.query(Lexicon)
            .filter(Lexicon.category == category)
            .all()
        ]
    return categories
# ============= EOF =============================================
