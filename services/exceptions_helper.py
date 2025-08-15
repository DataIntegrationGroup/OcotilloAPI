from fastapi import HTTPException


class PydanticStyleException(HTTPException):
    """
    Exception to be raised for errors not handled by Pydantic to maintain
    the same style.
    """

    def __init__(
        self,
        status_code: int,
        loc: list,
        msg: str,
        type: str,
        input: dict,
    ):
        super().__init__(
            status_code=status_code,
            detail=[{"loc": loc, "msg": msg, "type": type, "input": input}],
        )
