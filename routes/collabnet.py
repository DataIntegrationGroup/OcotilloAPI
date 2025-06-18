# ===============================================================================
# Copyright 2025 ross
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================
from fastapi import Depends, status
from fastapi.routing import APIRoute, APIRouter
from sqlalchemy import select
from sqlalchemy.orm import Session
from geoalchemy2 import functions as geofunc


from models import get_db_session, adder
from models.base import SampleLocation, Well
from models.collabnet import CollaborativeNetworkWell
from models.timeseries import GroundwaterLevelObservation, WellTimeseries
from schemas.collabnet import CreateCollaborativeNetworkWell

router = APIRouter(prefix="/collabnet", tags=["collabnet"])


@router.post("/add", status_code=status.HTTP_201_CREATED)
def add_collabnet_well(
    data: CreateCollaborativeNetworkWell,
    session: Session = Depends(get_db_session),
):
    """
    Add a well to the collaborative network.
    """
    return adder(session, CollaborativeNetworkWell, data)


@router.get("/stats")
def location_stats(session: Session = Depends(get_db_session)):
    """
    Get statistics about the collaborative network wells.
    """
    # sql = select(GroundwaterLevelObservation)

    # sql = sql.join(WellTimeseries)

    # sql = sql.join(CollaborativeNetworkWell)
    # sql = sql.join(Well)
    # sql = sql.outerjoin(GroundwaterLevelObservation)
    # sql = sql.join(WellTimeseries)
    # sql = sql.join(GroundwaterLevelObservation)

    # print(sql)
    # stats = session.execute(sql).all()

    sql = select(Well, CollaborativeNetworkWell)
    sql = sql.join(CollaborativeNetworkWell)

    wells = session.execute(sql).all()
    return {
        "total_wells": len(wells),
        "actively_monitored_wells": sum(
            1 for well, collab in wells if collab.actively_monitored
        ),
        # "locations": [loc.name for  in stats],
    }


@router.get("/location_feature_collection")
def get_location(session: Session = Depends(get_db_session)):
    """ """

    sql = select(
        SampleLocation, geofunc.ST_AsGeoJSON(SampleLocation.point).label("geojson")
    )
    sql = sql.join(Well)
    sql = sql.join(CollaborativeNetworkWell)

    # if query:
    #     sql = sql.where(make_query(SampleLocation, query))

    locations = session.execute(sql).all()

    def make_feature(location: SampleLocation, geojson: str):
        """
        Create a GeoJSON feature from a SampleLocation and its geojson representation.
        """
        return {
            "type": "Feature",
            "properties": {
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "wells": [well.id for well in location.well],
            },
            "geometry": geojson,
        }

    features = [make_feature(*args) for args in locations]

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ============= EOF =============================================
