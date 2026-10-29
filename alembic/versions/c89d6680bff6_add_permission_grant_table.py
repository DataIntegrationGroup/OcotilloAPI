"""add permission_grant table

Revision ID: c89d6680bff6
Revises: cab78adfe059
Create Date: 2026-10-28 23:03:54.547192

ADR5's permission_grant table (docs/vocabulary-and-scope-taxonomy.md).
`principal_type`, `capability`, and `scope_type` are lexicon-backed, so the
values this table needs (`user`/`principal_group`/`api_key`,
`read`/`create`/`update`/`delete`/`administer`,
`global`/`project`/`thing`/`program`) are inserted here by hand --
autogenerate only emits the column/FK shape, not the term data a fresh
deploy's lexicon seed doesn't have yet. `core/lexicon.json` carries the same
terms for a freshly seeded database; see the terms added there alongside
this migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c89d6680bff6"
down_revision: Union[str, Sequence[str], None] = "cab78adfe059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRINCIPAL_TYPE_CATEGORY = "principal_type"
PRINCIPAL_TYPE_TERMS = {
    "user": "An individual person, identified by audit trail only today.",
    "principal_group": "A named set of people, backed by Authentik group membership.",
    "api_key": "A credential with no person behind it.",
}

CAPABILITY_CATEGORY = "capability"
CAPABILITY_TERMS = {
    "read": "View data.",
    "create": "Create new records.",
    "update": "Edit existing records.",
    "delete": "Remove records.",
    "administer": "Manage grants themselves.",
}

SCOPE_TYPE_CATEGORY = "scope_type"
SCOPE_TYPE_TERMS = {
    "global": "No restriction -- scope_id is the literal '*'.",
    "project": "Scoped to one Group (db/group.py).",
    "thing": "Scoped to one Thing.",
    "program": "Scoped to one program, e.g. AMMP or Geothermal.",
}


def _insert_lexicon_category(connection, category: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO lexicon_category (name) VALUES (:name) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": category},
    )


def _insert_lexicon_terms(connection, category: str, terms: dict[str, str]) -> None:
    for term, definition in terms.items():
        connection.execute(
            sa.text(
                "INSERT INTO lexicon_term (term, definition) VALUES (:term, :definition) "
                "ON CONFLICT (term) DO NOTHING"
            ),
            {"term": term, "definition": definition},
        )
    connection.execute(
        sa.text("""
            INSERT INTO lexicon_term_category_association (term_id, category_id)
            SELECT t.id, c.id
            FROM lexicon_term t, lexicon_category c
            WHERE t.term = ANY(:terms) AND c.name = :category
            ON CONFLICT DO NOTHING
            """),
        {"terms": list(terms), "category": category},
    )


def upgrade() -> None:
    connection = op.get_bind()

    for category, terms in (
        (PRINCIPAL_TYPE_CATEGORY, PRINCIPAL_TYPE_TERMS),
        (CAPABILITY_CATEGORY, CAPABILITY_TERMS),
        (SCOPE_TYPE_CATEGORY, SCOPE_TYPE_TERMS),
    ):
        _insert_lexicon_category(connection, category)
        _insert_lexicon_terms(connection, category, terms)

    op.create_table(
        "permission_grant",
        sa.Column("principal_type", sa.String(length=100), nullable=False),
        sa.Column("principal_id", sa.String(length=255), nullable=False),
        sa.Column("capability", sa.String(length=100), nullable=False),
        sa.Column("scope_type", sa.String(length=100), nullable=False),
        sa.Column("scope_id", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=100), nullable=True),
        sa.Column("field_group", sa.String(length=100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("granted_by", sa.String(length=255), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
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
        ["principal_type", "principal_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_permission_grant_principal", table_name="permission_grant")
    op.drop_table("permission_grant")

    # Lexicon terms are left in place -- they may be adopted elsewhere by the
    # time this is reversed, and an unused term is harmless where a missing
    # one breaks a foreign key (matches b2c3d4e5f6a7's convention).
