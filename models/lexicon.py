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
from sqlalchemy import String
from sqlalchemy.orm import mapped_column

from models import AutoBaseMixin, Base


class Lexicon(Base, AutoBaseMixin):
    """
    Lexicon model for storing terms and their definitions.
    This model can be extended to include additional fields as needed.
    """

    term = mapped_column(String(100), unique=True, nullable=False)
    definition = mapped_column(String(255), nullable=False)
    category = mapped_column(String(255), nullable=True)

    def __repr__(self):
        return f"<Lexicon(category={self.category}, term={self.term}, definition={self.definition})>"


# ============= EOF =============================================
