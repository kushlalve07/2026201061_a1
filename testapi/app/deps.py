"""FastAPI dependencies that hand the shared database adapters to the routers."""
from __future__ import annotations

from fastapi import Request

from app.db import Mongo, Postgres


def get_pg(request: Request) -> Postgres:
    return request.app.state.pg


def get_mongo(request: Request) -> Mongo:
    return request.app.state.mongo
