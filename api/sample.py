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
# from typing import List
#
# from fastapi import APIRouter, Depends, status
# from sqlalchemy import select
# from sqlalchemy.orm import Session
#
# from db.engine import get_db_session
# from db.series import TimeObservation, TimeSeries, SampleWellAssociation
# from db.sample import Sample
# from schemas.response.timeseries import WellTimeseriesResponse
# from schemas.create.timeseries import (
#     CreateTimeSeries,
#     CreateSample,
#     CreateTimeObservation,
# )
#
# router = APIRouter(
#     prefix="/sample",
# )
#
#
# @router.post(
#     "/time_series/add",
#     status_code=status.HTTP_201_CREATED,
# )
# def add_sample_timeseries(
#     timeseries_data: CreateTimeSeries, session: Session = Depends(get_db_session)
# ):
#
#     timeseries = TimeSeries(**timeseries_data.model_dump())
#     session.add(timeseries)
#     session.commit()
#     return timeseries
#
#
# @router.post("/add",
#              status_code=status.HTTP_201_CREATED, summary="Add Sample")
# def add_sample(
#     sample_data: CreateSample,
#     session: Session = Depends(get_db_session),
# ):
#     """
#     Endpoint to add a sample.
#     """
#     data = sample_data.model_dump()
#     well_id = data.pop("well_id", None)
#     sample = Sample(**data)
#     if well_id:
#         sample_well_association = SampleWellAssociation()
#         sample_well_association.well_id = well_id
#         sample_well_association.sample = sample
#         session.add(sample_well_association)
#
#     session.add(sample)
#     session.commit()
#     # return sample
#
#
# @router.post(
#     "/time_series/observations/add",
#     status_code=status.HTTP_201_CREATED,
#     summary="Add Sample Timeseries Observations",
# )
# def add_sample_observations(
#     observations: List[CreateTimeObservation],
#     session: Session = Depends(get_db_session),
# ):
#     """
#     Endpoint to add observations to a sample timeseries.
#     """
#     obs = []
#     for observation in observations:
#         data = observation.model_dump()
#         ts = TimeObservation(**data)
#
#         session.add(ts)
#         obs.append(ts)
#
#     session.commit()
#     return obs
#
#
# # =======get endpoints ========
# @router.get("/samples/well/{well_id}", summary="Get Samples for Well ID")
# def get_well_samples(
#     well_id: int,
#     session: Session = Depends(get_db_session),
# ):
#     """
#     Endpoint to retrieve samples associated with a well.
#     """
#     sql = select(Sample)
#     sql = sql.join(SampleWellAssociation)
#     sql = sql.where(SampleWellAssociation.well_id == well_id)
#     return session.execute(sql).scalars().all()
#
#
# @router.get("/time_series/well/{well_id}")
# def get_well_timeseries(
#     well_id: int,
#     session: Session = Depends(get_db_session),
# ):
#     """
#     Endpoint to retrieve well timeseries.
#     """
#     sql = select(TimeSeries)
#     sql = sql.join(TimeObservation)
#     sql = sql.join(Sample)
#     sql = sql.join(SampleWellAssociation)
#     # sql = select(SampleWellAssociation)
#
#     sql = sql.where(SampleWellAssociation.well_id == well_id)
#     return session.execute(sql).scalars().all()
#     # timeseries = session.query(TimeSeries).filter(TimeSeries.type == "well").all()
#     # return WellTimeseriesResponse(timeseries=timeseries)
#
# @router.get(
#     "/time_series/{time_series_id}/observations",
# )
# def get_timeseries_observations(
#     time_series_id: int,
#     session: Session = Depends(get_db_session),
# ):
#     """
#     Endpoint to retrieve observations for a specific timeseries.
#     """
#     sql = select(TimeObservation).where(TimeObservation.time_series_id == time_series_id)
#
#     return session.execute(sql).scalars().all()
# # @router.post(
# #     "/well",
# #     response_model=WellTimeseriesResponse,
# #     summary="Add Well Timeseries",
# #     status_code=status.HTTP_201_CREATED,
# # )
# # def add_well_timeseries(
# #     well_timeseries_data: CreateWellTimeseries, session=Depends(get_db_session)
# # ):
# #     """
# #     Endpoint to add a well timeseries.
# #     """
# #
# #     ts = WellTimeseries(**well_timeseries_data.model_dump())
# #     session.add(ts)
# #     session.commit()
# #
# #     return ts
# #
# #
# # @router.post(
# #     "/well/groundwater_level/observations",
# #     status_code=status.HTTP_201_CREATED,
# #     summary="Add groundwater level observation",
# # )
# # def add_well_observations(
# #     observations: List[CreateGroundwaterLevelObservation],
# #     session=Depends(get_db_session),
# # ):
# #     """
# #     Endpoint to add observations to a well timeseries.
# #     """
# #     for observation in observations:
# #         ts = GroundwaterLevelObservation(**observation.model_dump())
# #         session.add(ts)
# #
# #     session.commit()
# #     return {"message": "Observations added successfully."}
#
#
# # ============= EOF =============================================
