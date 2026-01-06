"""
Pydantic models for the Notes table.
"""

from core.enums import NoteType

from pydantic import BaseModel
from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel

# -------- BASE SCHEMA: ----------
"""
Defines the core, shared attributes of a Note for reuse.
"""


class BaseNote(BaseModel):
    note_type: NoteType
    content: str


# -------- CREATE ----------
class CreateNote(BaseCreateModel, BaseNote):
    # TODO: this was a suggestion by AI, but based on our other schemas it
    # seems like more should be added here...
    """
    Schema for creating a new Note. The parent object's ID and type will be
    taken from the URL path, not the request body.
    """
    pass


# -------- RESPONSE ----------
class NoteResponse(BaseResponseModel, BaseNote):
    """
    Response schema for Note details.
    """

    target_id: int
    target_table: str


# -------- UPDATE ----------
class UpdateNote(BaseUpdateModel):
    """
    Schema for updating an existing Note. All fields are optional
    """

    note_type: str | None = None
    content: str | None = None
