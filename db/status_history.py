"""
models/status_history.py

This model defines the `StatusHistory` table, a central, polymorphic log for
all time-variant operational statuses (e.g., Use Status, Access Status).

**NOTE**: This is a polymorphic table. It does not define outgoing relationships
itself. Instead, other tables (like Thing and Location) use the `StatusHistoryMixin`
mixin to establish a One-to-Many relationship TO this table.
"""

from datetime import date

from sqlalchemy import (
    Integer,
    String,
    Text,
    and_,
)
from sqlalchemy.orm import Mapped, mapped_column, declared_attr, relationship, foreign

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term


class StatusHistory(Base, AutoBaseMixin, ReleaseMixin):
    status_type: Mapped[str] = lexicon_term(nullable=False)
    status_value: Mapped[str] = lexicon_term(nullable=False)
    start_date: Mapped[date] = mapped_column(nullable=False)
    end_date: Mapped[date] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Polymorphic relationship columns
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_table: Mapped[str] = mapped_column(String(50), nullable=False)


class StatusHistoryMixin:
    """
    Mixin for models that can have a status history (e.g., Thing, Location).
    It automatically creates a polymorphic One-to-Many relationship to the
    StatusHistory table.
    """

    @declared_attr
    def status_history(cls):
        return relationship(
            "StatusHistory",
            primaryjoin=and_(
                cls.id == foreign(StatusHistory.target_id),
                StatusHistory.target_table == cls.__tablename__,
            ),
            cascade="all, delete-orphan",
            lazy="selectin",
        )
