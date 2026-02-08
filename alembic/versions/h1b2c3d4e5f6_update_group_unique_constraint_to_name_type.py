"""update group uniqueness from name to (name, group_type)

Revision ID: h1b2c3d4e5f6
Revises: 7b8c9d0e1f2a
Create Date: 2026-02-07 13:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7b8c9d0e1f2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_unique_constraints() -> list[dict]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.get_unique_constraints("group")


def _drop_name_only_unique_constraints() -> None:
    # Drop any existing unique constraint that enforces uniqueness on name only.
    for constraint in _existing_unique_constraints():
        columns = constraint.get("column_names") or []
        name = constraint.get("name")
        if name and columns == ["name"]:
            op.drop_constraint(name, "group", type_="unique")


def _ensure_no_duplicate_name_group_type_pairs() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(sa.text("""
            SELECT name, group_type, COUNT(*) AS cnt
            FROM "group"
            WHERE group_type IS NOT NULL
            GROUP BY name, group_type
            HAVING COUNT(*) > 1
            LIMIT 1
            """)).first()
    if duplicate:
        raise RuntimeError(
            "Cannot create uq_group_name_type: duplicate (name, group_type) rows exist."
        )


def _ensure_no_duplicate_names() -> None:
    bind = op.get_bind()
    duplicate = bind.execute(sa.text("""
            SELECT name, COUNT(*) AS cnt
            FROM "group"
            GROUP BY name
            HAVING COUNT(*) > 1
            LIMIT 1
            """)).first()
    if duplicate:
        raise RuntimeError(
            "Cannot recreate uq_group_name: duplicate group names exist."
        )


def upgrade() -> None:
    _drop_name_only_unique_constraints()
    _ensure_no_duplicate_name_group_type_pairs()

    constraint_names = {
        c.get("name") for c in _existing_unique_constraints() if c.get("name")
    }
    if "uq_group_name_type" not in constraint_names:
        op.create_unique_constraint(
            "uq_group_name_type", "group", ["name", "group_type"]
        )


def downgrade() -> None:
    constraint_names = {
        c.get("name") for c in _existing_unique_constraints() if c.get("name")
    }
    if "uq_group_name_type" in constraint_names:
        op.drop_constraint("uq_group_name_type", "group", type_="unique")

    _ensure_no_duplicate_names()

    constraint_names = {
        c.get("name") for c in _existing_unique_constraints() if c.get("name")
    }
    if "uq_group_name" not in constraint_names:
        op.create_unique_constraint("uq_group_name", "group", ["name"])
