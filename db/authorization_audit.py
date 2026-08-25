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
db/authorization_audit.py

The append-only log of authorization events: grants, revocations, consent
captured or withdrawn, destinations registered or retired.

ADR5 asks for this from the first commit, for one reason: when something is
exposed that should not have been, the first question is never "what was the
value". It is "who granted that, and when".

Append only. Nothing in the application updates or deletes a row here, and a
database-level backstop for writes that bypass the application is still owed
(ADR5, 4.3). ``AuditMixin.created_at`` is the event time; there is no second
timestamp column to disagree with it.

Separate from sqlalchemy-continuum's versioning, which records data history.
Authorization changes are a different, higher-value target.
"""

from typing import Optional

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, AutoBaseMixin

# Event types. Strings rather than lexicon terms: the log must be able to
# record an event whose vocabulary row was itself just deleted.
GRANT_CREATED = "grant.created"
GRANT_REVOKED = "grant.revoked"
CONSENT_RECORDED = "consent.recorded"
CONSENT_REVOKED = "consent.revoked"
DESTINATION_REGISTERED = "destination.registered"


class AuthorizationAudit(Base, AutoBaseMixin):
    """One authorization event, as it happened."""

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Who did it, as the identifier the application had at the time.
    actor: Mapped[str] = mapped_column(String(255), nullable=False)

    # What it happened to: table name and row id, kept as loose values so a
    # deleted row does not take its own audit trail with it.
    subject_table: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # The event's own fields, whatever they were. What each event should
    # record is open (PERM-U11); recording the payload keeps the question
    # answerable later rather than losing it now.
    detail: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __str__(self):
        return (
            f"{self.event_type} {self.subject_table}:{self.subject_id} by {self.actor}"
        )


# ============= EOF =============================================
