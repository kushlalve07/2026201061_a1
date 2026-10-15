from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import Postgres
from app.deps import get_pg
from app.pagination import PageParams, page_params
from app.schemas.audit import WalletAudit
from app.schemas.common import Page
from app.schemas.riders import RiderDetail, RiderItem
from app.services import audit as audit_service
from app.services import riders as service

router = APIRouter(prefix="/riders", tags=["riders"])


@router.get("", response_model=Page[RiderItem], summary="Browse riders (also feeds the 'acting as' picker)")
def list_riders(
    search: str | None = Query(None, max_length=100, description="part of the rider's name"),
    has_active_trip: bool | None = Query(None),
    page: PageParams = Depends(page_params),
    pg: Postgres = Depends(get_pg),
):
    return service.list_riders(pg, page, search=search, has_active_trip=has_active_trip)


@router.get("/{rider_id}", response_model=RiderDetail, summary="One rider with active and recent trips")
def get_rider(rider_id: UUID, pg: Postgres = Depends(get_pg)):
    return service.get_rider(pg, rider_id)


@router.get(
    "/{rider_id}/wallet-audit",
    response_model=WalletAudit,
    summary="Read-only audit trail with running balance (dates are inclusive, UTC)",
)
def wallet_audit(
    rider_id: UUID,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    order: Literal["asc", "desc"] = Query("asc"),
    page: PageParams = Depends(page_params),
    pg: Postgres = Depends(get_pg),
):
    return audit_service.wallet_audit(pg, rider_id, page, date_from=date_from, date_to=date_to, order=order)
