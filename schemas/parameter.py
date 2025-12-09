from schemas import BaseResponseModel
from core.enums import ParameterType, ParameterName, Unit


# -------- RESPONSE -------
class ParameterResponse(BaseResponseModel):
    """
    Pydantic model for the response of a parameter.
    This model can be extended to include additional fields as needed.
    """

    parameter_name: ParameterName
    matrix: str
    parameter_type: ParameterType | None
    cas_number: str | None
    default_unit: Unit | None
