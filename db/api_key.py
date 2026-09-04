# ===============================================================================
# Copyright 2026
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
Personal API keys for the /ogcapi-internal mount.

Replaces the operator-issued digests in the INTERNAL_OGC_API_KEYS environment
variable for new keys. Those still work -- see core/internal_ogc_auth.py -- but
revoking one requires a redeploy, which is the problem this table exists to
solve.

See docs/api-key-management.md.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, AutoBaseMixin
from domain.api_key import SCOPE_OGC_INTERNAL


class ApiKey(Base, AutoBaseMixin):
    """A credential a user issued for themselves from the settings page.

    Deliberately not `db.permission.Permission`, which is a landowner's consent
    to site access and shares nothing with this but the word.

    No ReleaseMixin: a credential is not draft-or-published content, and giving
    it a release_status would put it in front of the release filters that read
    that column.
    """

    # The token itself is never stored. Only this digest is, so a database dump
    # does not hand over working credentials.
    # Uniqueness comes from ix_api_key_token_digest below, not from a
    # column-level unique=True -- that would emit a second unique index on the
    # same column.
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    # Leading and trailing characters only -- enough for the owner to tell two
    # keys apart in the list, useless as a credential.
    token_preview: Mapped[str] = mapped_column(String(32), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Authentik's `sub` claim. Ownership, which is what every route filters on.
    #
    # Kept separate from AuditMixin's created_by_id even though the two hold the
    # same value today: that column records who performed the write, and an
    # admin-issued-on-behalf-of path would set the two differently. Conflating
    # them would silently reassign the key.
    owner_sub: Mapped[str] = mapped_column(String(255), nullable=False)

    # Display only. There is no user table to join, so the name is denormalized
    # at creation and may go stale if the person renames themselves upstream.
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    scope: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SCOPE_OGC_INTERNAL
    )

    # NOT NULL: every key expires. domain.api_key.expiry_for() sets it, and
    # domain.api_key.is_expired() reads a NULL as expired, so a row written
    # around the create path fails closed instead of living forever.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Soft revocation. The row survives so last_used_at and the audit columns
    # survive with it -- "when was this compromised key last used" is the
    # question you need answered after you revoke, not before.
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Written at most once per domain.api_key.LAST_USED_RESOLUTION, so paging
    # through a collection does not write once per page.
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # The authentication lookup. Every /ogcapi-internal request carrying a
        # key hits this, so it is the one index that has to exist.
        Index("ix_api_key_token_digest", "token_digest", unique=True),
        # The list route: one user's keys, newest first.
        Index("ix_api_key_owner_sub", "owner_sub"),
    )

    def __str__(self):
        return f"{self.name} ({self.token_preview})"


# ============= EOF =============================================
