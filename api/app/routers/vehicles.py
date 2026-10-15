from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import Mongo, Postgres
from app.deps import get_mongo, get_pg
from app.pagination import PageParams, page_params
from app.schemas.vehicles import VehicleDetail, VehiclePage
from app.services import vehicles as service

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=VehiclePage, summary="Browse vehicles with lifetime stats (materialized view)")
def list_vehicles(
    search: str | None = Query(None, max_length=20, description="part of the licence plate"),
    vehicle_class: str | None = Query(None, alias="class", max_length=30),
    is_active: bool | None = Query(None),
    sort: Literal["plate", "earnings", "trips"] = Query("plate"),
    page: PageParams = Depends(page_params),
    pg: Postgres = Depends(get_pg),
):
    return service.list_vehicles(
        pg, page, search=search, vehicle_class=vehicle_class, is_active=is_active, sort=sort
    )


@router.get("/classes", response_model=list[str], summary="Distinct vehicle classes (for filters)")
def vehicle_classes(pg: Postgres = Depends(get_pg)):
    return service.vehicle_classes(pg)


@router.get("/{vehicle_id}", response_model=VehicleDetail, summary="One vehicle with stats and revenue rank")
def get_vehicle(vehicle_id: UUID, pg: Postgres = Depends(get_pg)):
    return service.get_vehicle(pg, vehicle_id)


@router.get(
    "/{vehicle_id}/metadata",
    response_model=dict[str, Any],
    summary="The flexible VehicleMetadata catalog document (MongoDB)",
)
def get_metadata(vehicle_id: UUID, pg: Postgres = Depends(get_pg), mongo: Mongo = Depends(get_mongo)):
    return service.get_metadata(pg, mongo, vehicle_id)
