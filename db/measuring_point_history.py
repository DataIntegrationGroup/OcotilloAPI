"""
SQLAlchemy model for the MeasuringPointHistory table.

This table stores the authoritative MP height of a Thing from
construction or modification events. It provides a complete, auditable
history of the official, surveyed measuring point (MP) descriptions
and heights for a Thing.

This table is not for storing routine field checks of the
MP height (which are stored on the `Observation` table). This table should
only be updated when a well is first installed, physically modified
(e.g., a new wellhead is installed), or officially re-surveyed.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, ForeignKey, Date, Text, Numeric
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin

if TYPE_CHECKING:
    from db.thing import Thing


class MeasuringPointHistory(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, authoritative, time-stamped record of a
    Thing's measuring point description and height.
    """

    # --- Foreign Keys ---
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id", ondelete="CASCADE"), nullable=False
    )

    # --- Columns ---
    measuring_point_height: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
        comment="The official, surveyed height of the measuring point relative to ground surface (in feet).",
    )
    mp_description: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="A clear description of the measuring point (e.g., 'North side of casing, top of PVC', 'Top of new steel collar').",
    )
    start_date: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
        comment="The date this measuring point configuration became effective.",
    )
    end_date: Mapped[Date] = mapped_column(
        Date,
        nullable=True,
        comment="The date this measuring point configuration was superseded. A `NULL` value indicates this is the current, active, and authoritative record for the `Thing`.",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Describes the reason for the new or updated measuring point (e.g., 'A new wellhead was installed').",
    )

    # --- Relationships ---
    # Many-To-One: A description history record belongs to one Thing. Many history records may belong to a single Thing.
    thing: Mapped["Thing"] = relationship("Thing", back_populates="mp_history")
