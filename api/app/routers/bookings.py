from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.db import Postgres
from app.deps import get_pg
from app.schemas.bookings import BookingRequest, BookingResult
from app.services import bookings as service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post(
    "",
    response_model=BookingResult,
    status_code=201,
    summary="Workflow 1: book a trip with sp_atomic_booking",
    responses={
        400: {"model": BookingResult, "description": "Rolled back: fare must be greater than 0"},
        404: {"model": BookingResult, "description": "Rolled back: rider or vehicle not found"},
        409: {"model": BookingResult, "description": "Rolled back: balance, active trip, inactive vehicle, concurrency"},
    },
)
def book(body: BookingRequest, pg: Postgres = Depends(get_pg)):
    http_status, result = service.book_trip(pg, body.rider_id, body.vehicle_id, body.fare_amount)
    payload = BookingResult.model_validate(result)
    return JSONResponse(status_code=http_status, content=jsonable_encoder(payload))
