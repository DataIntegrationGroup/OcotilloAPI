from schemas import BaseResponseModel


# -------- RESPONSE -------
class ParameterResponse(BaseResponseModel):
    """
    Pydantic model for the response of a parameter.
    This model can be extended to include additional fields as needed.
    """

    parameter_name: str
    matrix: str
    parameter_type: str | None
    cas_number: str | None
    default_unit: str
