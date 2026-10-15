from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import RiderRef, TripStatus, VehicleRef


class TripItem(BaseModel):
    id: UUID
    rider: RiderRef
    vehicle: VehicleRef
    fare_amount: float
    status: TripStatus
    created_at: datetime
    next_status: TripStatus | None


class TripDetail(TripItem):
    review: dict[str, Any] | None


class StatusChange(BaseModel):
    status: TripStatus
