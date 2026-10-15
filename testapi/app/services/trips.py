"""Trips: browse, detail, and the REQUESTED -> IN_TRANSIT -> COMPLETED transitions."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection

from app.db import Mongo, Postgres
from app.db.sql import Filters, like_pattern
from app.errors import ApiError, not_found
from app.pagination import PageParams
from app.services import reviews as review_service

NEXT_STATUS = {"REQUESTED": "IN_TRANSIT", "IN_TRANSIT": "COMPLETED"}
ACTIVE_STATUSES = ("REQUESTED", "IN_TRANSIT")

TRIP_COLUMNS = """
    t.id, t.fare_amount, t.status, t.created_at,
    r.id AS rider_id, r.name AS rider_name,
    v.id AS vehicle_id, v.license_plate, v.class AS vehicle_class
"""
TRIP_FROM = """
    FROM trips t
    JOIN riders r   ON r.id = t.rider_id
    JOIN vehicles v ON v.id = t.vehicle_id
"""


def trip_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "rider": {"id": row["rider_id"], "name": row["rider_name"]},
        "vehicle": {
            "id": row["vehicle_id"],
            "license_plate": row["license_plate"],
            "vehicle_class": row["vehicle_class"],
        },
        "fare_amount": row["fare_amount"],
        "status": row["status"],
        "created_at": row["created_at"],
        "next_status": NEXT_STATUS.get(row["status"]),
    }


def fetch_trip(conn: Connection, trip_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(f"SELECT {TRIP_COLUMNS} {TRIP_FROM} WHERE t.id = %s", (trip_id,)).fetchone()
    return trip_from_row(row) if row else None


def list_trips(
    pg: Postgres,
    page: PageParams,
    *,
    search: str | None = None,
    status: str | None = None,
    rider_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    f = Filters()
    if search:
        f.add("(r.name ILIKE %(q)s OR v.license_plate ILIKE %(q)s)", q=like_pattern(search))
    if status == "ACTIVE":
        f.add("t.status IN ('REQUESTED', 'IN_TRANSIT')")
    elif status:
        f.add("t.status = %(status)s", status=status)
    if rider_id:
        f.add("t.rider_id = %(rider_id)s", rider_id=rider_id)
    if vehicle_id:
        f.add("t.vehicle_id = %(vehicle_id)s", vehicle_id=vehicle_id)
    if date_from:
        f.add("t.created_at >= %(date_from)s", date_from=date_from)
    if date_to:
        f.add("t.created_at < %(date_to_excl)s", date_to_excl=date_to + timedelta(days=1))

    with pg.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n {TRIP_FROM} {f.where}", f.params).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT {TRIP_COLUMNS} {TRIP_FROM} {f.where}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**f.params, "limit": page.limit, "offset": page.offset},
        ).fetchall()
    return page.wrap([trip_from_row(r) for r in rows], total)


def get_trip(pg: Postgres, mongo: Mongo, trip_id: UUID) -> dict[str, Any]:
    with pg.connection() as conn:
        trip = fetch_trip(conn, trip_id)
    if trip is None:
        raise not_found("Trip", trip_id)
    trip["review"] = review_service.review_for_trip(mongo, trip_id)
    return trip


def advance_status(pg: Postgres, trip_id: UUID, new_status: str) -> dict[str, Any]:
    """Calls fn_advance_trip_status (sql/07); the database enforces the allowed order."""
    with pg.connection() as conn:
        try:
            conn.execute("SELECT id FROM fn_advance_trip_status(%s, %s)", (trip_id, new_status))
        except psycopg.errors.NoDataFound:
            raise not_found("Trip", trip_id) from None
        except psycopg.errors.InvalidParameterValue as exc:
            hint = exc.diag.message_hint
            message = exc.diag.message_primary or "That status change is not allowed."
            raise ApiError(409, "INVALID_TRANSITION", f"{message} ({hint})" if hint else message) from None
        trip = fetch_trip(conn, trip_id)
    assert trip is not None
    return trip
