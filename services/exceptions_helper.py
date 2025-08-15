from fastapi import HTTPException
from typing import TypedDict


class PydanticDetailDict(TypedDict):
    loc: list
    msg: str
    type: str
    input: dict


class PydanticStyleException(HTTPException):
    """
    Exception to be raised for errors not handled by Pydantic to maintain
    the same style.
    """

    def __init__(
        self,
        status_code: int,
        detail: list[PydanticDetailDict],
    ):
        """
        The detail needs to be a list with the following keys:
            "loc": list
            "msg": string
            "type": string
            "input": Any
        """
        super().__init__(
            status_code=status_code,
            detail=detail,
        )
