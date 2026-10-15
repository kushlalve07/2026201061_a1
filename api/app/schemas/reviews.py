from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RatingCount(BaseModel):
    rating: int
    count: int


class TagCount(BaseModel):
    tag: str
    count: int


class ReviewSummary(BaseModel):
    vehicle_id: UUID | None
    total: int
    overall_average: float | None
    rating_distribution: list[RatingCount]
    top_tags: list[TagCount]


class ReviewItem(BaseModel):
    id: str
    trip_id: str
    rider_id: str | None
    vehicle_id: str | None
    license_plate: str | None
    rating: int
    tags: list[str]
    comment: str | None
    created_at: datetime
