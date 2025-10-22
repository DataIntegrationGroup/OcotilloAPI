"""
Pydantic models for the Notes table.
"""

from pydantic import BaseModel
from schemas import BaseCreateModel, BaseUpdateModel, BaseResponseModel

# -------- BASE SCHEMA: ----------
"""
Defines the core, shared attributes of a Note for reuse.
"""


class BaseNote:
    note_type: str
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

    note_id: int
    notable_id: int
    notable_type: str


# -------- UPDATE ----------
class UpdateNote(BaseUpdateModel):
    """
    Schema for updating an existing Note. All fields are optional
    """

    note_type: str | None = None
    content: str | None = None
