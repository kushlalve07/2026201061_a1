from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import Mongo, Postgres
from app.deps import get_mongo, get_pg
from app.pagination import PageParams, page_params
from app.schemas.common import Page
from app.schemas.trips import StatusChange, TripDetail, TripItem
from app.services import trips as service

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=Page[TripItem], summary="Browse trips (newest first)")
def list_trips(
    search: str | None = Query(None, max_length=100, description="rider name or licence plate"),
    status: Literal["REQUESTED", "IN_TRANSIT", "COMPLETED", "ACTIVE"] | None = Query(None),
    rider_id: UUID | None = Query(None),
    vehicle_id: UUID | None = Query(None),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    page: PageParams = Depends(page_params),
    pg: Postgres = Depends(get_pg),
):
    return service.list_trips(
        pg,
        page,
        search=search,
        status=status,
        rider_id=rider_id,
        vehicle_id=vehicle_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{trip_id}", response_model=TripDetail, summary="One trip with its review (MongoDB)")
def get_trip(trip_id: UUID, pg: Postgres = Depends(get_pg), mongo: Mongo = Depends(get_mongo)):
    return service.get_trip(pg, mongo, trip_id)


@router.patch(
    "/{trip_id}/status",
    response_model=TripItem,
    summary="Advance a trip one step: REQUESTED -> IN_TRANSIT -> COMPLETED",
    responses={404: {"description": "Unknown trip"}, 409: {"description": "Transition not allowed"}},
)
def advance_status(trip_id: UUID, body: StatusChange, pg: Postgres = Depends(get_pg)):
    return service.advance_status(pg, trip_id, body.status)
