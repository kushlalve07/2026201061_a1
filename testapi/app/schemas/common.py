from __future__ import annotations

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")

TripStatus = Literal["REQUESTED", "IN_TRANSIT", "COMPLETED"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int


class RiderRef(BaseModel):
    id: UUID
    name: str


class VehicleRef(BaseModel):
    id: UUID
    license_plate: str
    vehicle_class: str


class TripRef(BaseModel):
    id: UUID
    status: TripStatus


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
