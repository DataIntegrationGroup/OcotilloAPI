"""add the api_key table

Personal API keys for the /ogcapi-internal mount, issued by users from the
settings page rather than by an operator.

The mount already accepts a static key, but those live as `label:sha256hex`
entries in the INTERNAL_OGC_API_KEYS environment variable, rendered from a
Secret Manager secret at deploy time. Two consequences motivated this table:
revoking a key requires a redeploy, and a key is attributable to a person only
by an unenforced label. Rows here are owned by an Authentik `sub` and revoke on
the next request.

Only the SHA-256 digest of a token is stored, never the token, so a dump of
this table hands over no working credentials. `token_preview` holds the leading
and trailing characters so the owner can tell two keys apart in the list.

`expires_at` is NOT NULL -- every key expires, 365 days out by default and by
ceiling. `revoked_at` is a soft revocation: the row stays so `last_used_at`
survives revocation, since "when was this compromised key last used" is a
question that only comes up afterwards.

Revision ID: d0e1f2a3b4c5
Revises: b3c4d5e6f7a9
Create Date: 2026-08-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_key",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("token_preview", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_sub", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        # AuditMixin
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("created_by_name", sa.String(length=255), nullable=True),
        sa.Column("created_by_id", sa.String(length=255), nullable=True),
        sa.Column("updated_by_name", sa.String(length=255), nullable=True),
        sa.Column("updated_by_id", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # The authentication lookup: every keyed request to /ogcapi-internal hits
    # this one. Unique both to enforce the obvious and to keep it a single-row
    # index probe.
    op.create_index("ix_api_key_token_digest", "api_key", ["token_digest"], unique=True)
    # The list route: one owner's keys.
    op.create_index("ix_api_key_owner_sub", "api_key", ["owner_sub"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_api_key_owner_sub", table_name="api_key")
    op.drop_index("ix_api_key_token_digest", table_name="api_key")
    op.drop_table("api_key")


# ============= EOF =============================================
