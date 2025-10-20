"""
SQLAlchemy model for the Notes table.

This is a polymorphic table for storing all unstructured notes, categorized by
a note_type.

The Notes table should be used when a record might need more than one note,
when the notes need to be categorized, or when you need the ability to
search across all notes in the system. This is different from a dedicated
notes field on a specific table, which should be used to store a simple,
single-purpose attribute of the record itself.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Text, and_, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column, foreign

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    from db.thing import Thing
    from db.location import Location


class Notes(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, categorized note that can be attached to various
    parent objects throughout the database.
    """

    # --- Polymorphic Columns ---
    notable_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="The ID of the parent record this note is about (e.g., a `thing_id`, `location_id`, etc).",
    )
    notable_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="The type of the note associated with this record.",
    )

    # --- Columns ---
    note_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field that defines the specific category of the note (e.g. 'Access Instructions`, ",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are viewonly relationships used by the 'target' property below.
    _thing_target: Mapped["Thing"] = relationship(
        "Thing",
        primaryjoin=and_(foreign(notable_id) == Thing.id, notable_type == "Thing"),
        viewonly=True,
    )
    _location_target: Mapped["Location"] = relationship(
        "Location",
        primaryjoin=and_(
            foreign(notable_id) == Location.id, notable_type == "Location"
        ),
        viewonly=True,
    )

    @property
    def target(self):
        """
        A generic property to get the parent object (Thing, Location, etc.).

        This is useful for simplifying application code by providing a single,
        consistent way to access the parent of a polymorphic record without
        needing to check the 'notable_type' field manually.
        """
        return getattr(self, f"_{self.notable_type.lower()}_target")

        # --- Table Arguments ---
        # A composite index to optimize retrieval of all note records for a specific parent object.

    __table_args__ = (Index("ix_notes_polymorphic_link", "notable_id", "notable_type"),)
