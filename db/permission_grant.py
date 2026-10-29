"""
ADR5's permission_grant table: internal staff authorization, recording
which principal holds which capability within which scope.

See docs/vocabulary-and-scope-taxonomy.md for the vocabulary this
implements.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import AutoBaseMixin, Base, lexicon_term


class PermissionGrant(Base, AutoBaseMixin):
    """A grant of one capability to one principal within one scope.

    `principal_id`/`scope_id` are plain strings, no foreign key -- what
    they reference varies by type. Validated in code, not the database.
    """

    principal_type: Mapped[str] = lexicon_term(nullable=False)
    principal_id: Mapped[str] = mapped_column(String(255), nullable=False)

    capability: Mapped[str] = lexicon_term(nullable=False)

    scope_type: Mapped[str] = lexicon_term(nullable=False)

    # Never NULL -- `global` uses the literal "*" rather than blank, so an
    # omitted value fails this constraint instead of granting global access.
    scope_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Nullable -- no concrete value list exists yet for either; not
    # hardcoded enums.
    data_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    field_group: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    granted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


# ============= EOF =============================================
