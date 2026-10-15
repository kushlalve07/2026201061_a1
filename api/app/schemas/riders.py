from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import TripRef
from app.schemas.trips import TripItem


class RiderItem(BaseModel):
    id: UUID
    name: str
    wallet_balance: float
    active_trip: TripRef | None


class RiderDetail(BaseModel):
    id: UUID
    name: str
    wallet_balance: float
    active_trip: TripItem | None
    recent_trips: list[TripItem]
    audit_entries: int
