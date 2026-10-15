"""Application factory.  Run:  uvicorn app.main:app --port 8000"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.db import Mongo, Postgres
from app.errors import install_error_handlers
from app.routers import ALL_ROUTERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pg = Postgres(settings.pg_conninfo)
        app.state.pg.open()
        app.state.mongo = Mongo(settings.mongo_uri, settings.mongo_database)
        try:
            yield
        finally:
            app.state.pg.close()
            app.state.mongo.close()

    app = FastAPI(
        title="RideSync API",
        version="1.0.0",
        description="Thin HTTP layer over the RideSync PostgreSQL + MongoDB backend (CS6.302 Assignment 2).",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)
    for router in ALL_ROUTERS:
        app.include_router(router, prefix="/api")
    return app


app = create_app()
