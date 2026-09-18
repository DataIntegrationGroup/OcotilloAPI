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
"""
db/destination.py

The registry of places data goes: the anonymous public web, a federal
harvester, a partner agency's standing connection.

A destination is not a user and not a role. It is the other half of a
publication consent row -- the "to whom" a landowner agreed to. Adding a new
one is a registry entry plus a set of consent rows, which is the point of
having a registry at all (ADR5, Part IV).
"""

from typing import Optional

from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, AutoBaseMixin, lexicon_term


class Destination(Base, AutoBaseMixin):
    """One place published data is offered to."""

    # Stable, URL-safe handle. Routes and consent records refer to a
    # destination by slug rather than id so a fixture, a config file, and an
    # operator all name it the same way.
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_kind: Mapped[str] = lexicon_term(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Retiring a destination stops it being offered without deleting the
    # consent history that says what was once agreed to.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __str__(self):
        return self.slug


# ============= EOF =============================================
