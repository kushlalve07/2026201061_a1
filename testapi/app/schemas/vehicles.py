from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import Page


class VehicleItem(BaseModel):
    id: UUID
    license_plate: str
    vehicle_class: str
    is_active: bool
    lifetime_trip_count: int
    total_earnings: float


class VehiclePage(Page[VehicleItem]):
    stats_as_of: datetime | None


class VehicleDetail(VehicleItem):
    revenue_rank: int | None
    ranked_vehicles: int
    stats_as_of: datetime | None
