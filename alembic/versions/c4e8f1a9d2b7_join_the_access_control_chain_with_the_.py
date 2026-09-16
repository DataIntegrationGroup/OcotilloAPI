"""join the access control chain with the chemistry collection-date rebuild

Revision ID: c4e8f1a9d2b7
Revises: ed62fbdb7d7a, 3f9c1b7d2a64
Create Date: 2026-09-15 09:12:00.000000

Empty by design, for the same reason as ed62fbdb7d7a. Merging staging into this
branch brought in 3f9c1b7d2a64, which rebuilds the two materialized chemistry
views on the collection date; this branch's head is ed62fbdb7d7a, ending the
access-control chain. The two touch disjoint relations -- b4c5d6e7f8a9 rebuilds
the well views and states that the chemistry collections are left alone -- so
there is nothing to reconcile, but `alembic upgrade head` will not pick between
two heads on its own.

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "c4e8f1a9d2b7"
down_revision: Union[str, Sequence[str], None] = ("ed62fbdb7d7a", "3f9c1b7d2a64")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
