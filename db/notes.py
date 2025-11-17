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

from sqlalchemy import Integer, Text, Index, and_
from sqlalchemy.orm import relationship, Mapped, mapped_column, declared_attr, foreign

from db.base import Base, AutoBaseMixin, ReleaseMixin, lexicon_term

if TYPE_CHECKING:
    pass


class Notes(Base, AutoBaseMixin, ReleaseMixin):
    """
    Represents a single, categorized note that can be attached to various
    parent objects throughout the database.
    """

    # --- Polymorphic Columns ---
    target_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="The ID of the parent record this note is about (e.g., a `thing_id`, `location_id`, etc).",
    )
    target_table: Mapped[str] = mapped_column()
    # notable_type: Mapped[str] = lexicon_term(
    #     nullable=False,
    #     comment="The type of the note associated with this record.",
    # )

    # --- Columns ---
    note_type: Mapped[str] = lexicon_term(
        nullable=False,
        comment="A controlled vocabulary field that defines the specific category of the note (e.g. 'Access Instructions`, ",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Polymorphic Parent Relationships (Internal) ---
    # These are viewonly relationships used by the 'target' property below.
    # _thing_target: Mapped["Thing"] = relationship(
    #     "Thing",
    #     primaryjoin="and_(foreign(Notes.target_id) == Thing.id, Notes.target_table == 'thing')",
    #     viewonly=True,
    # )
    # _location_target: Mapped["Location"] = relationship(
    #     "Location",
    #     primaryjoin="and_(foreign(Notes.target_id) == Location.id, Notes.target_table == 'location')",
    #     viewonly=True,
    # )

    @property
    def target(self):
        """
        A generic property to get the parent object (Thing, Location, etc.).

        This is useful for simplifying application code by providing a single,
        consistent way to access the parent of a polymorphic record without
        needing to check the 'notable_type' field manually.
        """
        return getattr(self, f"_{self.target_table.lower()}_target")

        # --- Table Arguments ---
        # A composite index to optimize retrieval of all note records for a specific parent object.

    __table_args__ = (Index("ix_notes_polymorphic_link", "target_id", "target_table"),)


class NotesMixin:
    """
    Mixin for models that can have multiple types or categories of notes.
    It automatically creates a polymorphic One-to-Many relationship to the
    Notes table.
    """

    @declared_attr
    def notes(cls):
        """
        The high-performance, declarative relationship for reading notes.
        This provides a polymorphic one-to-many link to the Notes table.

        PERFORMANCE NOTE: Use with `selectinload` in queries to prevent the
        N+1 query problem when accessing notes for multiple parent objects.
        """
        return relationship(
            "Notes",
            primaryjoin=and_(
                cls.id == foreign(Notes.target_id),
                Notes.target_table == cls.__name__,
            ),
            cascade="all, delete-orphan",
            lazy="selectin",
            overlaps="notes",
        )

    def add_note(
        self,
        content: str,
        note_type: str,
        release_status: str = "draft",
        created_by: str = None,
    ) -> Notes:
        """
        A convenient factory method to create a new Note associated with this object.
        This provides a clean, object-oriented API for writing.
        """

        return Notes(
            content=content,
            note_type=note_type,
            target_id=self.id,
            target_table=self.__class__.__name__,
            release_status=release_status,
        )

    def _get_notes(self, note_type: str) -> list[Notes]:
        return [n for n in self.notes if n.note_type == note_type]
