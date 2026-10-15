from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import Postgres
from app.deps import get_pg
from app.pagination import PageParams, page_params
from app.schemas.analytics import FleetSummary, RankingItem, RefreshResult, RevenueTrend
from app.schemas.common import Page
from app.services import analytics as service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/fleet-summary", response_model=FleetSummary, summary="Totals from the materialized view")
def fleet_summary(pg: Postgres = Depends(get_pg)):
    return service.fleet_summary(pg)


@router.post(
    "/fleet-summary/refresh",
    response_model=RefreshResult,
    summary="REFRESH MATERIALIZED VIEW CONCURRENTLY (logged in mv_refresh_log)",
)
def refresh_fleet_summary(pg: Postgres = Depends(get_pg)):
    return service.refresh_fleet_summary(pg)


@router.get("/revenue-ranking", response_model=Page[RankingItem], summary="DENSE_RANK() over lifetime revenue")
def revenue_ranking(page: PageParams = Depends(page_params), pg: Postgres = Depends(get_pg)):
    return service.revenue_ranking(pg, page)


@router.get(
    "/vehicles/{vehicle_id}/revenue-trend",
    response_model=RevenueTrend,
    summary="Daily revenue + 7-day moving average for one vehicle (Part A window query)",
)
def revenue_trend(
    vehicle_id: UUID,
    days: int = Query(30, ge=7, le=365, description="window length, ending on the vehicle's last revenue day"),
    zero_fill: bool = Query(False, description="count days without completed trips as $0 (handover note #8)"),
    pg: Postgres = Depends(get_pg),
):
    return service.revenue_trend(pg, vehicle_id, days=days, zero_fill=zero_fill)
