"""add ui_surface to permission_grant

A grant could reach data. Now it can also open a screen: `ui_surface` names a
navigation item or page in the admin UI, using the same resource identifier the
UI already checks, so a term and a nav item cannot drift apart.

`data_type` becomes nullable to make room for it. That does **not** relax the
no-wildcard rule -- a grant still names exactly one subject, and the XOR between
`data_type` and `ui_surface` is enforced in domain/access.py before any row is
written, along with the rule that a surface grant is always global. The rules
live there rather than in a check constraint so they hold for every writer and
read as one sentence; see db/permission_grant.py.

Existing rows all carry a data_type and are untouched: nothing in the table
means "all", before or after this migration.

`ui_surface` is a lexicon category seeded from core/lexicon.json by
init_lexicon, not an enum type, so adding a screen later is not a migration.

Revision ID: a396d7d9928d
Revises: ed62fbdb7d7a
Create Date: 2026-08-27 18:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a396d7d9928d"
down_revision: Union[str, Sequence[str], None] = "ed62fbdb7d7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "permission_grant",
        sa.Column("ui_surface", sa.String(length=100), nullable=True),
    )
    op.create_foreign_key(
        "fk_permission_grant_ui_surface_lexicon_term",
        "permission_grant",
        "lexicon_term",
        ["ui_surface"],
        ["term"],
        onupdate="CASCADE",
    )
    op.alter_column("permission_grant", "data_type", nullable=True)


def downgrade() -> None:
    # A surface grant has no data_type to fall back to, so it cannot survive a
    # column that is NOT NULL again. Dropping those rows is the honest
    # downgrade: they are grants this schema has no way to express, and
    # leaving them with an invented data_type would grant data access nobody
    # asked for.
    op.execute("DELETE FROM permission_grant WHERE ui_surface IS NOT NULL")
    op.alter_column("permission_grant", "data_type", nullable=False)
    op.drop_constraint(
        "fk_permission_grant_ui_surface_lexicon_term",
        "permission_grant",
        type_="foreignkey",
    )
    op.drop_column("permission_grant", "ui_surface")


# ============= EOF =============================================
