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
# from fastapi import APIRouter, Depends
# from fastapi_pagination.ext.sqlalchemy import paginate
# from sqlalchemy import select
# from sqlalchemy.orm import Session
# from starlette.status import HTTP_201_CREATED
#
# from api.pagination import CustomPage
# from core.dependencies import session_dependency
# from db import adder
# from db.engine import get_db_session
# from db.series.series import Series
# from schemas_v2.series import SeriesResponse, CreateSeries
# from services.query_helper import paginated_all_getter
#
# router = APIRouter(
#     prefix="/series",
#     tags=["series"],
# )
#
#
# # ============= Get ==============================================
# @router.get(
#     "",
# )
# def get_series(
#     session: session_dependency,
#     thing_id: int = None,  # Optional filter for a specific thing
#     observed_property: str = None,  # Optional filter for observed property
#     sensor_id: int = None,  # Optional filter for sensor ID
# ) -> CustomPage[SeriesResponse]:
#     """
#     Endpoint to retrieve series data.
#     """
#     if thing_id is not None or observed_property is not None:
#         sql = select(Series)
#         if thing_id is not None:
#             sql = sql.where(Series.thing_id == thing_id)
#         if observed_property is not None:
#             sql = sql.where(Series.observed_property == observed_property)
#         if sensor_id is not None:
#             sql = sql.where(Series.sensor_id == sensor_id)
#
#         return paginate(conn=session, query=sql)
#
#     return paginated_all_getter(session, Series)
#
#
# @router.get("/{series_id}")
# def get_series_by_id(
#     series_id: int, session: Session = Depends(get_db_session)
# ) -> SeriesResponse:
#     """
#     Endpoint to retrieve a specific series by its ID.
#     """
#
#     return session.get(Series, series_id)
#
#
# # ============= Post =============================================
# @router.post("", status_code=HTTP_201_CREATED)
# def add_series(
#     series_data: CreateSeries, session: Session = Depends(get_db_session)
# ) -> SeriesResponse:
#     """
#     Endpoint to add a new series.
#     """
#     return adder(session, Series, series_data)
#
#
# # ============= EOF =============================================
