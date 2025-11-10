"""
models/status_history.py

This model defines the `StatusHistory` table, a central, polymorphic log for
all time-variant operational statuses (e.g., Use Status, Access Status).

**NOTE**: This is a polymorphic table. It does not define outgoing relationships
itself. Instead, other tables (like Thing and Location) use the `StatusHistoryMixin`
mixin to establish a One-to-Many relationship TO this table.
"""

import datetime

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term


class StatusHistory(Base, AutoBaseMixin, ReleaseMixin):
    status_type: Mapped[str] = lexicon_term(nullable=False)
    status_value: Mapped[str] = lexicon_term(nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_date: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Polymorphic relationship columns
    statusable_id: Mapped[int] = mapped_column(Integer, nullable=False)
    statusable_type: Mapped[str] = mapped_column(String(50), nullable=False)
