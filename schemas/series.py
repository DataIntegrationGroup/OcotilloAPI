# # ===============================================================================
# # Copyright 2025 ross
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# # http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.
# # ===============================================================================
# from pydantic import BaseModel
# from core.enums import ReleaseStatus
#
#
# # -------- CREATE ----------
# class CreateSeries(BaseModel):
#     """
#     Schema for creating a new series.
#     This schema can be extended with additional fields as needed.
#     """
#
#     name: str
#     description: str | None = None
#     thing_id: int
#     sensor_id: int
#     observed_property: str
#     unit: str
#     release_status: ReleaseStatus | None = (
#         "draft"  # Default to 'draft', can be 'published' or 'archived'
#     )
#
#
# # -------- RESPONSE --------
# class SeriesResponse(BaseModel):
#     id: int
#     name: str
#     observed_property: str
#     thing_id: int
#
#
# # -------- UPDATE ----------
#
# # ============= EOF =============================================
