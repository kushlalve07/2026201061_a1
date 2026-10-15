"""One error shape for every failure: {"error": {"code", "message", "details"?}}."""
from __future__ import annotations

import logging
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pymongo.errors import ConnectionFailure
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("ridesync.api")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str, ident: Any) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} {ident} not found")


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=jsonable_encoder({"error": body}))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return error_response(422, "VALIDATION_ERROR", "Some of the request values are not valid.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else f"HTTP_{exc.status_code}"
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(psycopg.OperationalError)
    async def _postgres_down(_: Request, exc: Exception):
        log.warning("PostgreSQL unavailable: %s", exc)
        return error_response(503, "POSTGRES_UNAVAILABLE", "PostgreSQL is not responding. Please try again.")

    @app.exception_handler(ConnectionFailure)
    async def _mongo_down(_: Request, exc: Exception):
        log.warning("MongoDB unavailable: %s", exc)
        return error_response(503, "MONGO_UNAVAILABLE", "MongoDB is not responding. Please try again.")

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return error_response(500, "INTERNAL_ERROR", "Something went wrong on the server.")
