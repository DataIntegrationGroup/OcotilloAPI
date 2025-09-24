"""
This table is an installation log that creates a many-to-many relationship
between Things and Sensors, tracking which piece of hardware was installed
at which Thing and for what period of time.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, ForeignKey, Date, Numeric, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.thing import Thing
    from db.sensor import Sensor


class Deployment(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents the installation of a specific piece of equipment (Sensor) at a Thing
    for a defined period. This is an Association Object.
    """

    # --- Foreign Keys ---
    thing_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("thing.id"), nullable=False
    )
    sensor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sensor.id"), nullable=False
    )

    # --- Columns ---
    installation_date: Mapped[Date] = mapped_column(Date, nullable=False)
    removal_date: Mapped[Date] = mapped_column(Date, nullable=True)
    recording_interval: Mapped[int] = mapped_column(Integer, nullable=True)
    recording_interval_units: Mapped[str] = lexicon_term(nullable=True)
    hanging_cable_length: Mapped[float] = mapped_column(Numeric, nullable=True)
    hanging_point_height: Mapped[float] = mapped_column(Numeric, nullable=True)
    hanging_point_description: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    # Many-To-One: A Deployment is for one Thing.
    thing: Mapped["Thing"] = relationship("Thing", back_populates="deployments")
    # Many-To-One: A Deployment is of one piece of equipment (sensor).
    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="deployments")
