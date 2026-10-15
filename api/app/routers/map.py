from fastapi import APIRouter, Depends, Query

from app.db import Mongo, Postgres
from app.deps import get_mongo, get_pg
from app.schemas.map import NearbyResult, SimulateRequest, SimulateResult
from app.services import map as service

router = APIRouter(prefix="/map", tags=["map"])


@router.get(
    "/nearby-vehicles",
    response_model=NearbyResult,
    summary="Workflow 3: nearest available vehicles ($geoNear), one per vehicle, nearest first",
)
def nearby_vehicles(
    lng: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    radius_m: int = Query(5000, ge=100, le=20000),
    limit: int = Query(20, ge=1, le=50),
    pg: Postgres = Depends(get_pg),
    mongo: Mongo = Depends(get_mongo),
):
    return service.nearby_vehicles(mongo, pg, lng=lng, lat=lat, radius_m=radius_m, limit=limit)


@router.post(
    "/pings/simulate",
    response_model=SimulateResult,
    status_code=201,
    summary="Insert fresh demo pings near a point (seeded pings expire after 2 h)",
)
def simulate_pings(body: SimulateRequest, pg: Postgres = Depends(get_pg), mongo: Mongo = Depends(get_mongo)):
    return service.simulate_pings(mongo, pg, lng=body.lng, lat=body.lat, count=body.count)
