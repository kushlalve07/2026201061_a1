from fastapi import APIRouter, Depends

from app.db import Mongo, Postgres
from app.deps import get_mongo, get_pg
from app.schemas.health import Health
from app.services import health as service

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Health, summary="Reachability of PostgreSQL and MongoDB")
def health(pg: Postgres = Depends(get_pg), mongo: Mongo = Depends(get_mongo)):
    return service.check(pg, mongo)
