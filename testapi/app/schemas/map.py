from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lng: float
    lat: float


class NearbyVehicle(BaseModel):
    vehicle_id: str
    license_plate: str | None
    vehicle_class: str | None
    distance_m: float
    location: GeoPoint
    last_ping_at: datetime


class NearbyResult(BaseModel):
    origin: GeoPoint
    radius_m: int
    items: list[NearbyVehicle]
    generated_at: datetime


class SimulateRequest(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    count: int = Field(10, ge=1, le=50)


class SimulateResult(BaseModel):
    inserted: int
    vehicle_ids: list[str]
