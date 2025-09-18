from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import mapped_column, relationship, Mapped

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term


class FieldEvent(Base, AutoBaseMixin, ReleaseMixin):
    """
    This table serves as the master log for all field visits. Each
    record in this table represents a single, continuous collection event at a
    specific Thing (e.g., a well) by a specific person on a specific date.

    This table's purpose is to store event-level metadata that is true for the
    entire visit, such as the date, time, and the person responsible. It acts as
    the parent container for all activities performed and all samples collected
    during that single visit.
    """

    # Foreign Keys
    thing_id: Mapped[int] = mapped_column(
        ForeignKey("thing.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to the Thing (e.g., sampling location) table.",
    )

    # Columns
    # TODO: do we want to have a list of all present at the field event, or is it enough to capture the event_lead_name and sampler_name(s)? (AMP user research)
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Date and time of the field event.",
    )
    event_lead_name: Mapped[str] = mapped_column(
        nullable=False, comment="The name of the person leading the field event"
    )
    # TODO: ask AMP if they care about this field. Is it needed? user research
    collecting_organization: Mapped[str] = lexicon_term(
        nullable=False,
        comment="The organization that is collecting and storing the samples from the field event",
    )
    notes: Mapped[str] = mapped_column(
        nullable=True,
        comment="Notes or comments about the field event.",
    )
    # Relationships
    thing: Mapped["Thing"] = relationship(back_populates="field_events")  # noqa: F821
    field_activities: Mapped[list["FieldActivity"]] = relationship(
        back_populates="field_event"
    )


class FieldActivity(Base, AutoBaseMixin, ReleaseMixin):
    """
    This table serves as a log of the specific, distinct tasks
    performed during a single `FieldEvent`. Its purpose is to correctly model
    the one-to-many relationship where a single field visit can have multiple
    objectives (e.g., collecting a water level and also collecting a water
    sample for the lab).

    Each record in this table represents one type of work, such as
    'groundwater level', 'geochemical', or 'water chemistry'. By linking a
    Sample record to a specific FieldActivity, the schema creates a clear and
    unambiguous chain of custody, ensuring that every observation can be traced
    back to the precise task that generated it.
    """

    # Foreign Keys
    field_event_id: Mapped[int] = mapped_column(
        ForeignKey("field_event.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to the FieldEvent table.",
    )

    # Columns
    activity_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="The type of activity performed during the field event (e.g., 'groundwater level', 'water chemistry', 'geothermal').",
    )
    notes: Mapped[str] = mapped_column(
        nullable=True,
        comment="Notes or comments about the field activity.",
    )

    # Relationships
    field_event: Mapped["FieldEvent"] = relationship(back_populates="field_activities")
    samples: Mapped[list["Sample"]] = relationship(  # noqa: F821
        back_populates="field_activity"
    )
