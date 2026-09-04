"""join the embargo chain with the field operations layer

Revision ID: ed62fbdb7d7a
Revises: b4c5d6e7f8a9, e1f2a3b4c5d6
Create Date: 2026-09-03 08:55:25.493341

Empty by design. This branch and staging both grew a migration from
c9d0e1f2a3b4: the access-control chain ending in b4c5d6e7f8a9 here, and
e1f2a3b4c5d6 (the water well field operations layer, #914) there. Two heads is
not a conflict -- they touch different relations -- but `alembic upgrade head`
refuses to guess between them, which is what aborted the BDD suite's before_all
hook with "Multiple head revisions are present".

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "ed62fbdb7d7a"
down_revision: Union[str, Sequence[str], None] = ("b4c5d6e7f8a9", "e1f2a3b4c5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
