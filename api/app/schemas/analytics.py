from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import VehicleRef
from app.schemas.vehicles import VehicleItem


class FleetSummary(BaseModel):
    total_vehicles: int
    active_vehicles: int
    lifetime_trips: int
    total_earnings: float
    avg_earnings_per_vehicle: float
    top_vehicles: list[VehicleItem]
    last_refreshed_at: datetime | None
    last_refresh_duration_ms: float | None


class RefreshResult(BaseModel):
    refreshed_at: datetime
    duration_ms: float


class RankingItem(BaseModel):
    revenue_rank: int
    vehicle_id: UUID
    license_plate: str
    vehicle_class: str
    total_revenue: float


class TrendPoint(BaseModel):
    day: date
    daily_total: float
    moving_avg_7day: float
    has_trips: bool


class RevenueTrend(BaseModel):
    vehicle: VehicleRef
    revenue_rank: int | None
    total_revenue: float | None
    date_from: date
    date_to: date
    days: int
    zero_fill: bool
    points: list[TrendPoint]
