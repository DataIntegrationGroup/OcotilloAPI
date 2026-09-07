"""add the access-control tables

The storage half of ADR5: two grant tables, one destination registry, one
append-only authorization audit log. Nothing reads them yet except
services/visibility.py and the /publication routes; no existing endpoint
changes behavior.

* ``destination`` -- where published data is offered: the public web, a
  harvester, a partner agency.
* ``permission_grant`` -- internal authorization, principal x capability x
  scope, one row per data type. No NULL-as-wildcard: a grant names its type.
* ``publication_consent`` -- what a landowner agreed to publish about their
  well, per destination and data type. One live row per combination; revoked
  rows stay, which is why the unique index is partial.
* ``authorization_audit`` -- every grant, revocation and consent event, append
  only, so "who granted that, and when" has an answer.

The vocabularies (principal_type, capability, grant_scope_type,
access_data_type, destination_kind) are lexicon categories seeded from
core/lexicon.json by init_lexicon, not enum types, so adding a destination
kind is not a migration.

Revision ID: 79a3ab24627e
Revises: e7c1a9f4b2d8
Create Date: 2026-08-24 22:09:54.479541

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "79a3ab24627e"
down_revision: Union[str, Sequence[str], None] = "e7c1a9f4b2d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "authorization_audit",
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("subject_table", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
    op.create_table(
        "destination",
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("destination_kind", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["destination_kind"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "permission_grant",
        sa.Column("principal_type", sa.String(length=100), nullable=False),
        sa.Column("principal_id", sa.String(length=255), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("scope_type", sa.String(length=100), nullable=False),
        sa.Column("scope_id", sa.Integer(), nullable=True),
        sa.Column("data_type", sa.String(length=100), nullable=False),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("ends_at", sa.Date(), nullable=True),
        sa.Column("granted_by", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["capability"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["data_type"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["principal_type"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scope_type"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_permission_grant_principal",
        "permission_grant",
        ["principal_type", "principal_id", "capability"],
        unique=False,
    )
    op.create_table(
        "publication_consent",
        sa.Column("thing_id", sa.Integer(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(length=100), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.Date(), nullable=False),
        sa.Column("ends_at", sa.Date(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
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
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact.id"],
        ),
        sa.ForeignKeyConstraint(
            ["data_type"], ["lexicon_term.term"], onupdate="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["destination.id"],
        ),
        sa.ForeignKeyConstraint(["thing_id"], ["thing.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_publication_consent_live",
        "publication_consent",
        ["thing_id", "destination_id", "data_type"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_publication_consent_live", table_name="publication_consent")
    op.drop_table("publication_consent")
    op.drop_index("ix_permission_grant_principal", table_name="permission_grant")
    op.drop_table("permission_grant")
    op.drop_table("destination")
    op.drop_table("authorization_audit")
