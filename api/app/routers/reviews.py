from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import Mongo, Postgres
from app.deps import get_mongo, get_pg
from app.pagination import PageParams, page_params
from app.schemas.common import Page
from app.schemas.reviews import ReviewItem, ReviewSummary
from app.services import reviews as service

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get(
    "/summary",
    response_model=ReviewSummary,
    summary="Workflow 4 $facet: rating distribution, top tags, overall average",
)
def review_summary(vehicle_id: UUID | None = Query(None), mongo: Mongo = Depends(get_mongo)):
    return service.summary(mongo, vehicle_id)


@router.get("", response_model=Page[ReviewItem], summary="Reviews, newest first")
def list_reviews(
    vehicle_id: UUID | None = Query(None),
    rating: int | None = Query(None, ge=1, le=5),
    page: PageParams = Depends(page_params),
    pg: Postgres = Depends(get_pg),
    mongo: Mongo = Depends(get_mongo),
):
    return service.list_reviews(mongo, pg, page, vehicle_id=vehicle_id, rating=rating)
