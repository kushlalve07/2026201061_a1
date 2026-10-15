from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.trips import TripItem

# DECIMAL(10,2) range. The sign is deliberately NOT checked here: a fare <= 0
# is rejected by sp_atomic_booking itself (reason INVALID_FARE).
MAX_FARE = Decimal("99999999.99")


class BookingRequest(BaseModel):
    rider_id: UUID
    vehicle_id: UUID
    fare_amount: Decimal = Field(ge=-MAX_FARE, le=MAX_FARE)


class AuditEntry(BaseModel):
    id: UUID
    timestamp: datetime
    action_type: Literal["CREDIT", "DEBIT"]
    amount_changed: float
    balance_after: float


BookingReason = Literal[
    "INSUFFICIENT_BALANCE",
    "ACTIVE_TRIP_EXISTS",
    "VEHICLE_INACTIVE",
    "NOT_FOUND",
    "INVALID_FARE",
    "CONCURRENT_UPDATE",
    "BOOKING_FAILED",
]


class BookingResult(BaseModel):
    status: Literal["COMMITTED", "ROLLED_BACK"]
    reason: BookingReason | None
    message: str = Field(description="p_status exactly as returned by sp_atomic_booking")
    fare_amount: float
    trip: TripItem | None
    balance_before: float | None
    balance_after: float | None
    audit_entry: AuditEntry | None
    active_trip_id: UUID | None
