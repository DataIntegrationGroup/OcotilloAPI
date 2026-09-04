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
db/permission_grant.py

Internal authorization: may this principal exercise this capability within
this scope? (ADR5, Part III.)

This is institutional trust, decided per person by data services staff. The
landowner's half -- what an owner agreed to publish about their well -- is
``db/publication_consent.py``, a separate table with separate governance and
the same grammar. Both are evaluated by ``services/visibility.py``.

Invariants, enforced in ``domain/access.py`` before a row is written:

* ``data_type`` is never null and there is no term meaning "all", so a data
  type added later is not covered by an existing grant.
* A ``global`` grant carries no ``scope_id``; a ``group`` or ``thing`` grant
  requires one.
* Expiry is read at use. Nothing sweeps this table, so a missed job cannot
  leave a grant standing past its end date.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, AutoBaseMixin, lexicon_term


class PermissionGrant(Base, AutoBaseMixin):
    """One grant: principal x capability x scope, over one data type."""

    # --- Principal ---
    # principal_id is a stable identifier whose meaning depends on the type:
    # an Authentik subject for `user`, a group name for `role`, a key label
    # for `api key`. It is a string, not a foreign key, because Authentik owns
    # identity and Ocotillo owns authorization (ADR5, A.4).
    principal_type: Mapped[str] = lexicon_term(nullable=False)
    principal_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- What and where ---
    capability: Mapped[str] = lexicon_term(nullable=False)
    scope_type: Mapped[str] = lexicon_term(nullable=False)
    scope_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_type: Mapped[str] = lexicon_term(nullable=False)

    # --- When ---
    starts_at: Mapped[date] = mapped_column(nullable=False)
    ends_at: Mapped[Optional[date]] = mapped_column(nullable=True)

    # --- On whose authority ---
    # "Who granted that, and when" is the first question after an incident, so
    # it is a column rather than something to reconstruct from the audit log.
    granted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Revocation ---
    # Revoking sets these rather than deleting the row: the record that access
    # once existed is the point. Effective at the next read, never backdated.
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        # The read path always starts from "who is asking".
        Index(
            "ix_permission_grant_principal",
            "principal_type",
            "principal_id",
            "capability",
        ),
    )

    def __str__(self):
        return (
            f"{self.principal_type}:{self.principal_id} may {self.capability} "
            f"{self.data_type} ({self.scope_type})"
        )


# ============= EOF =============================================
